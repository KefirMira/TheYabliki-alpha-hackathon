from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.exc import SQLAlchemyError

from db.session import get_session_factory, unavailable
from schemas.company_analysis_api import CompanyAnalysisRequest, CreatedCompanyAnalysis
from services.company_analysis_service import (
    AnalysisFailure, CompanyAnalysisService, NewsNotAnalyzable, NewsNotFound,
    RunStatusUncertain, default_analyzer,
)
from services.company_profile_service import CompanyNotFound
from api.runtime import require_ai_enabled


router = APIRouter(prefix="/api/companies", tags=["company analyses"])


def get_analysis_analyzer():
    return default_analyzer


def get_analysis_service(sessions=Depends(get_session_factory), analyzer=Depends(get_analysis_analyzer)):
    return CompanyAnalysisService(sessions, analyzer)


@router.post("/{source_id}/analyses", response_model=CreatedCompanyAnalysis, status_code=201,
             dependencies=[Depends(require_ai_enabled)])
async def create_company_analysis(
    request: CompanyAnalysisRequest,
    source_id: str = Path(min_length=1, max_length=200),
    service: CompanyAnalysisService = Depends(get_analysis_service),
):
    return await _created_analysis(source_id, service.analyze(source_id, request.news.text, request.news.title))


@router.post("/{source_id}/news/{news_id}/analyses", response_model=CreatedCompanyAnalysis, status_code=201,
             dependencies=[Depends(require_ai_enabled)], responses={
                 404: {"description": "Company or saved news not found; no run created"},
                 422: {"description": "Invalid ID or saved content unavailable/over 100000 characters"},
                 502: {"description": "AI failed; run marked FAILED when possible"},
                 503: {"description": "AI disabled in demo, database/storage failure or uncertain run status"},
             })
async def analyze_saved_news(
    source_id: str = Path(min_length=1, max_length=200),
    news_id: int = Path(gt=0, le=9223372036854775807),
    service: CompanyAnalysisService = Depends(get_analysis_service),
):
    return await _created_analysis(source_id, service.analyze_saved(source_id, news_id))


async def _created_analysis(source_id, operation):
    try:
        saved = await operation
    except CompanyNotFound as error:
        raise HTTPException(404, detail={"code": "COMPANY_NOT_FOUND", "message": "Компания не найдена"}) from error
    except NewsNotFound as error:
        raise HTTPException(404, detail={"code": "NEWS_NOT_FOUND", "message": "Новость не найдена"}) from error
    except NewsNotAnalyzable as error:
        raise HTTPException(422, detail={"code": "NEWS_CONTENT_UNAVAILABLE",
            "message": "Нужен непустой текст новости длиной до 100000 символов."}) from error
    except RunStatusUncertain as error:
        raise HTTPException(503, detail={
            "code": error.code, "message": "Не удалось подтвердить статус запуска", "run_id": error.run_id,
        }) from error
    except AnalysisFailure as error:
        ai_failed = error.code == "AI_ANALYSIS_FAILED"
        raise HTTPException(502 if ai_failed else 503, detail={
            "code": error.code,
            "message": "Не удалось выполнить AI-анализ" if ai_failed else "Не удалось сохранить анализ",
            "run_id": error.run_id,
        }) from error
    except (SQLAlchemyError, OSError, TimeoutError) as error:
        raise unavailable() from error
    return CreatedCompanyAnalysis(
        run_id=saved.run_id, insight_id=saved.insight_id, news_id=saved.news_id,
        company_id=source_id, analysis=saved.result.analysis,
    )
