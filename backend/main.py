
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel
from services.rag_service import analyze_with_rag

load_dotenv()

app = FastAPI(title="Alfa Hack API")

client = AsyncOpenAI(
    api_key=os.environ["LLM_API_KEY"],
    base_url=os.environ["LLM_BASE_URL"],
    timeout=60.0
)

MODEL = os.environ["LLM_MODEL"]


class AnalyzeRequest(BaseModel):
    news: str


class AnalyzeResponse(BaseModel):
    analysis: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты финансовый аналитик. "
                        "Объясняй возможное влияние "
                        "экономических новостей на бизнес. "
                        "Не выдумывай факты."
                    )
                },
                {
                    "role": "user",
                    "content": request.news
                }
            ],
            max_tokens=500
        )

        return AnalyzeResponse(
            analysis=response.choices[0].message.content or ""
        )

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Не удалось получить ответ от LLM"
        )


@app.post("/api/analyze-rag")
async def analyze_rag(request: AnalyzeRequest):
    try:
        result = await analyze_with_rag(request.news)
        return result

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Ошибка при выполнении RAG-анализа"
        )
