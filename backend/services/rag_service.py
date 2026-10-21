
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from services.chunk_service import load_chunks
from services.search_service import search_chunks


BASE_DIR = Path(__file__).resolve().parent.parent

# Загружаем настройки подключения к LLM
load_dotenv(BASE_DIR / ".env")

client = AsyncOpenAI(
    api_key=os.environ["LLM_API_KEY"],
    base_url=os.environ["LLM_BASE_URL"],
    timeout=120.0
)

MODEL = os.environ["LLM_MODEL"]


async def analyze_with_rag(
    question: str,
    search_query: str | None = None
) -> dict:
    """
    Анализирует вопрос с использованием RAG.

    question — полный запрос для LLM.
    search_query — отдельный запрос для поиска.
    """

    json_path = (
        BASE_DIR / "data" / "processed" / "policy_rate.json"
    )

    # Загружаем подготовленные фрагменты PDF
    chunks = load_chunks(str(json_path))

    # Для поиска используем отдельный запрос,
    # если он передан
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
            "analysis": "В документах не найден подходящий контекст.",
            "sources": []
        }

    # Формируем контекст для LLM
    context_parts = []

    for index, chunk in enumerate(
        relevant_chunks,
        start=1
    ):
        context_parts.append(
            f"[Источник {index}]\n"
            f"Документ: {chunk['source']}\n"
            f"Страница: {chunk['page']}\n"
            f"Текст:\n{chunk['text']}"
        )

    context = "\n\n".join(context_parts)

    # Отправляем запрос к LLM
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты финансовый аналитик. "
                    "Используй предоставленные материалы "
                    "Альфа-Банка для ответа на вопрос. "
                    "Не выдумывай факты или цифры. "
                    "Отделяй факты от предположений. "
                    "Ссылайся на номера источников. "
                    "Если данных недостаточно, сообщи об этом. "
                    "Отвечай кратко и по существу."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Вопрос:\n{question}\n\n"
                    f"Материалы:\n{context}"
                )
            }
        ],
        max_tokens=4000
    )

    choice = response.choices[0]

    # Отладочная информация
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

    return {
        "analysis": analysis,
        "sources": [
            {
                "id": index,
                "document": chunk["source"],
                "page": chunk["page"],
                "score": round(chunk["score"], 4)
            }
            for index, chunk in enumerate(
                relevant_chunks,
                start=1
            )
        ]
    }
