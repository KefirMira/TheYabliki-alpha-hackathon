
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from schemas.analysis import CompanyAnalysisResponse
from schemas.company import CompanyProfile

from api.companies import router as companies_router
from api.company_analyses import router as company_analyses_router
from api.insights import router as insights_router
from api.readiness import router as readiness_router
from api.news import router as news_router
from db.session import database_lifespan
from services.analysis_gateway import analyze_for_company, analyze_with_rag
from api.runtime import require_ai_enabled
from settings import execution_mode
from schemas.http_docs import HealthResponse, RAGResponse, LegacyError, APIError, ValidationResponse
from api.auth import router as auth_router, legacy_denied, AUTH_ERRORS
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import request_validation_exception_handler


# Настройки приложения
BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")
execution_mode()  # Invalid modes must never silently enable paid analysis.

app = FastAPI(title="Alfa Hack API", version="1.22.0", lifespan=database_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.environ.get("CORS_ORIGINS", "").split(",") if origin.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(companies_router)
app.include_router(company_analyses_router)
app.include_router(insights_router)
app.include_router(readiness_router)
app.include_router(news_router)
app.include_router(auth_router)


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request, error):
    # FastAPI normally echoes input, including a submitted password. Never do so.
    if request.url.path == '/api/auth/login':
        return JSONResponse(status_code=422, content={'detail': {
            'code':'INVALID_LOGIN_INPUT','message':'Invalid login request'}},
            headers={'Cache-Control':'no-store'})
    return await request_validation_exception_handler(request,error)


@app.middleware('http')
async def private_response_cache_policy(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


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

@app.get("/health", responses={200: {"model": HealthResponse}}, description="Liveness; не проверяет БД, RAG или LLM.")
async def health():
    return {"status": "ok"}


# -----------------------------
# Обычный анализ через LLM
# -----------------------------

@app.post(
    "/api/analyze",
    dependencies=[Depends(legacy_denied), Depends(require_ai_enabled)],
    response_model=AnalyzeResponse,
    responses={**AUTH_ERRORS, 502: {"model": LegacyError}, 503: {"model": APIError, "description": "AI_DISABLED_IN_DEMO"}},
    description="Legacy отключён: без действующей сессии 401, с сессией 403. Прежняя схема сохранена; платный обход через этот endpoint запрещён."
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

@app.post("/api/analyze-rag", dependencies=[Depends(legacy_denied), Depends(require_ai_enabled)],
    responses={**AUTH_ERRORS, 200: {"model": RAGResponse}, 502: {"model": LegacyError}, 503: {"model": APIError}},
    description="Legacy RAG отключён: без действующей сессии 401, с сессией 403. Прежняя схема сохранена; вызов модели недоступен.")
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
    dependencies=[Depends(legacy_denied), Depends(require_ai_enabled)],
    response_model=CompanyAnalysisResponse,
    responses={**AUTH_ERRORS, 422: {"model": ValidationResponse}, 502: {"model": LegacyError}, 503: {"model": APIError}},
    description="Legacy с профилем из тела отключён: без действующей сессии 401, с сессией 403. Подмена company_id не разрешает вызов модели."
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
