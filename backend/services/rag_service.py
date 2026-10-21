
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from services.chunk_service import load_chunks
from services.search_service import search_chunks


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

client = AsyncOpenAI(
    api_key=os.environ["LLM_API_KEY"],
    base_url=os.environ["LLM_BASE_URL"],
    timeout=120.0
)

MODEL = os.environ["LLM_MODEL"]


async def analyze_with_rag(question: str) -> dict:
    json_path = (
        BASE_DIR / "data" / "processed" / "policy_rate.json"
    )

    chunks = load_chunks(str(json_path))

    relevant_chunks = search_chunks(
        query=question,
        chunks=chunks,
        top_k=3
    )

    if not relevant_chunks:
        return {
            "analysis": "В документах не найден подходящий контекст.",
            "sources": []
        }

    context_parts = []

    for index, chunk in enumerate(relevant_chunks, start=1):
        context_parts.append(
            f"[Источник {index}]\n"
            f"Документ: {chunk['source']}\n"
            f"Страница: {chunk['page']}\n"
            f"Текст:\n{chunk['text']}"
        )

    context = "\n\n".join(context_parts)

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты финансовый аналитик. "
                    "Используй предоставленные материалы "
                    "для ответа на вопрос. "
                    "Не выдумывай факты или цифры. "
                    "Отделяй факты от предположений. "
                    "Ссылайся на номера источников. "
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

    print("\n========== LLM DEBUG ==========")
    print("Модель:", response.model)
    print("Причина завершения:", choice.finish_reason)
    print("Использование токенов:", response.usage)
    print("================================\n")

    analysis = choice.message.content or ""

    if choice.finish_reason == "length":
        print("ВНИМАНИЕ: ответ LLM обрезан по лимиту токенов.")

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
            for index, chunk in enumerate(relevant_chunks, start=1)
        ]
    }
