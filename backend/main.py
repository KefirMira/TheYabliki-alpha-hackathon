
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from schemas.analysis import CompanyAnalysisResponse
from schemas.company import CompanyProfile

from api.companies import router as companies_router
from api.company_analyses import router as company_analyses_router
from api.insights import router as insights_router
from api.readiness import router as readiness_router
from db.session import database_lifespan
from services.analysis_gateway import analyze_for_company, analyze_with_rag


# Настройки приложения
BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

app = FastAPI(title="Alfa Hack API", lifespan=database_lifespan)
app.include_router(companies_router)
app.include_router(company_analyses_router)
app.include_router(insights_router)
app.include_router(readiness_router)


# -----------------------------
# Схемы запросов и ответов
# -----------------------------

class AnalyzeRequest(BaseModel):
    news: str = Field(min_length=1)


class AnalyzeResponse(BaseModel):
    analysis: str


class CompanyAnalyzeRequest(BaseModel):
    news: str = Field(min_length=1)
    company: CompanyProfile


# -----------------------------
# Проверка работоспособности
# -----------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# -----------------------------
# Обычный анализ через LLM
# -----------------------------

@app.post(
    "/api/analyze",
    response_model=AnalyzeResponse
)
async def analyze(request: AnalyzeRequest):
    try:
        from openai import AsyncOpenAI

        async with AsyncOpenAI(
            api_key=os.environ["LLM_API_KEY"],
            base_url=os.environ["LLM_BASE_URL"],
            timeout=60.0,
        ) as client:
            response = await client.chat.completions.create(
                model=os.environ["LLM_MODEL"],
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


# -----------------------------
# RAG-анализ новости
# -----------------------------

@app.post("/api/analyze-rag")
async def analyze_rag(request: AnalyzeRequest):
    try:
        result = await analyze_with_rag(
            question=request.news,
            search_query=request.news
        )

        return result

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Ошибка при выполнении RAG-анализа"
        )


# -----------------------------
# Персонализированный анализ
# -----------------------------

@app.post(
    "/api/analyze-company",
    response_model=CompanyAnalysisResponse
)
async def analyze_company(
    request: CompanyAnalyzeRequest
):
    try:
        result = await analyze_for_company(
            news=request.news,
            company=request.company
        )

        return result

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error)
        )

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Ошибка при анализе новости для компании"
        )
