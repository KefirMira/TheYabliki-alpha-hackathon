
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from services.knowledge_base_service import load_knowledge_base
from services.search_service import search_chunks


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

client = AsyncOpenAI(
    api_key=os.environ["LLM_API_KEY"],
    base_url=os.environ["LLM_BASE_URL"],
    timeout=120.0
)

MODEL = os.environ["LLM_MODEL"]


# Даты из названий и содержания известных документов.
# Это метаданные нашей локальной базы знаний.
DOCUMENT_DATES = {
    "ALFA_Russian_Steels_1К21PreviewUpdate_15Apr2021.pdf": "2021-04-15",
    "FI_Strategy_3Q26_22072026.pdf": "2026-07-22",
    "Gold_digest_August26.pdf": "2026-08",
    "Inflation_tracker_02.pdf": "2026-09-02",
    "policy_rate.pdf": "2026-09-11",
    "Бонд_Бриф_14092026.pdf": "2026-09-14",
}


async def analyze_with_rag(
    question: str,
    search_query: str | None = None,
    *,
    include_evidence: bool = False,
) -> dict:
    """
    Анализирует запрос с использованием
    локальной базы аналитических документов.

    question — полный запрос к LLM.
    search_query — запрос для поиска фрагментов.
    """

    chunks = load_knowledge_base()

    query_for_search = (
        search_query
        if search_query is not None
        else question
    )

    relevant_chunks = search_chunks(
        query=query_for_search,
        chunks=chunks,
        top_k=3
    )

    if not relevant_chunks:
        return {
            "analysis": (
                "В документах не найден "
                "подходящий контекст."
            ),
            "sources": []
        }

    context_parts = []

    for index, chunk in enumerate(
        relevant_chunks,
        start=1
    ):
        document_name = chunk["source"]

        document_date = DOCUMENT_DATES.get(
            document_name,
            "Дата не указана"
        )

        context_parts.append(
            f"[Источник {index}]\n"
            f"Документ: {document_name}\n"
            f"Дата документа: {document_date}\n"
            f"Страница: {chunk['page']}\n"
            f"Фрагмент: {chunk.get('chunk_id', 1)}\n"
            f"Текст:\n{chunk['text']}"
        )

    context = "\n\n".join(context_parts)

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты финансовый аналитик, "
                    "который помогает оценивать влияние "
                    "новостей на бизнес компаний. "

                    "Используй предоставленные "
                    "аналитические материалы "
                    "как источники контекста. "

                    "Строго соблюдай правила: "

                    "1. Не выдумывай факты, цифры "
                    "или сведения о компании. "

                    "2. Различай факты из источников "
                    "и собственные аналитические выводы. "

                    "3. Учитывай дату каждого документа. "
                    "Не выдавай исторические данные "
                    "за актуальные. "

                    "4. Если источник относится к 2021 году, "
                    "используй его только как исторический "
                    "контекст, если вопрос не касается "
                    "именно этого периода. "

                    "5. Не делай выводов о конкретной "
                    "компании только на основании "
                    "общей отраслевой аналитики. "

                    "6. Ссылайся на источники "
                    "в формате [Источник 1]. "

                    "7. Если данных недостаточно, "
                    "прямо сообщай об этом. "

                    "8. Отвечай на русском языке, "
                    "кратко и по существу. "
                )
            },
            {
                "role": "user",
                "content": (
                    f"Запрос:\n{question}\n\n"
                    f"Аналитические материалы:\n{context}"
                )
            }
        ],
        max_tokens=4000
    )

    if not response.choices:
        raise RuntimeError(
            "LLM не вернула вариантов ответа."
        )

    choice = response.choices[0]

    print("\n========== LLM DEBUG ==========")
    print("Модель:", response.model)
    print("Причина завершения:", choice.finish_reason)
    print("Использование токенов:", response.usage)
    print("================================\n")

    analysis = choice.message.content or ""

    if choice.finish_reason == "length":
        print(
            "ВНИМАНИЕ: ответ LLM обрезан "
            "по лимиту токенов."
        )

    if not analysis.strip():
        raise RuntimeError(
            "LLM не вернула текст анализа. "
            f"Причина завершения: {choice.finish_reason}"
        )

    sources = []

    for index, chunk in enumerate(
        relevant_chunks,
        start=1
    ):
        document_name = chunk["source"]

        sources.append({
            "id": index,
            "document": document_name,
            "date": DOCUMENT_DATES.get(document_name),
            "page": chunk["page"],
            "chunk_id": chunk.get("chunk_id", 1),
            "score": round(chunk["score"], 4)
        })

    result = {
        "analysis": analysis,
        "sources": sources
    }
    if include_evidence:
        # Capture the exact fragments used in this call, never re-run retrieval.
        result["evidence"] = [
            {**source, "text": chunk["text"]}
            for source, chunk in zip(sources, relevant_chunks)
        ]
        result["model_name"] = response.model
    return result
