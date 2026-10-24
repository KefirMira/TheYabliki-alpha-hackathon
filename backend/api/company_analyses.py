from api.auth import company_write, current_actor, AUTH_ERRORS
from fastapi import APIRouter, Depends, HTTPException, Path, Response
from sqlalchemy.exc import SQLAlchemyError

from db.session import get_session_factory, unavailable
from schemas.company_analysis_api import CompanyAnalysisRequest, CreatedCompanyAnalysis
from services.company_analysis_service import (
    AnalysisFailure, CompanyAnalysisService, NewsNotAnalyzable, NewsNotFound,
    RunStatusUncertain, default_analyzer,
)
from services.company_profile_service import CompanyNotFound
from api.runtime import require_ai_enabled
from schemas.http_docs import ANALYSIS_ERRORS
from schemas.http_docs import APIError
from repositories.news_analysis_job_repository import AnalysisConflict
from services.company_context_service import CompanyContextExternalTransferBlocked


router = APIRouter(prefix="/api/companies", tags=["company analyses"], dependencies=[Depends(company_write)], responses=AUTH_ERRORS)


def get_analysis_analyzer():
    return default_analyzer


def get_analysis_service(sessions=Depends(get_session_factory), analyzer=Depends(get_analysis_analyzer), actor=Depends(current_actor)):
    return CompanyAnalysisService(sessions, analyzer, actor_id=actor.user_id)


@router.post("/{source_id}/analyses", response_model=CreatedCompanyAnalysis, status_code=201,
             dependencies=[Depends(require_ai_enabled)], responses=ANALYSIS_ERRORS,
             description="MANUAL-новость и новый запуск. news.text: 1–100000; title необязателен, до 500. Без идемпотентности; demo: 503. Контекст PostgreSQL запрещён для внешнего AI: 503 COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED до создания запуска.")
async def create_company_analysis(
    request: CompanyAnalysisRequest,
    source_id: str = Path(min_length=1, max_length=200),
    service: CompanyAnalysisService = Depends(get_analysis_service),
):
    return await _created_analysis(source_id, service.analyze(source_id, request.news.text, request.news.title))


@router.post("/{source_id}/news/{news_id}/analyses", response_model=CreatedCompanyAnalysis, status_code=201,
             dependencies=[Depends(require_ai_enabled)], responses={**ANALYSIS_ERRORS,
                 200: {'model': CreatedCompanyAnalysis, 'description': 'Сохранённый COMPLETED без нового AI, после membership/can_analyze/news grant. Demo блокирует и cache: 503 AI_DISABLED_IN_DEMO'},
                 409: {'model': APIError, 'description': 'RUNNING, требуется разрешение retry, лимит или проверка истории/неопределённого исхода'}},
             description="Сессия, can_analyze и news grant обязательны; grant проверяется до claim/cache. Атомарный claim пары. COMPLETED: 200 без AI; RUNNING: 409; FAILED требует административного разрешения. Максимум две попытки. Тело не требуется. Demo: 503 даже для COMPLETED, без обхода через capabilities. Для нового анализа контекст PostgreSQL запрещён внешнему AI: 503 COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED, claim откатывается.")
async def analyze_saved_news(
    response: Response,
    source_id: str = Path(min_length=1, max_length=200),
    news_id: int = Path(gt=0, le=9223372036854775807),
    service: CompanyAnalysisService = Depends(get_analysis_service),
):
    return await _created_analysis(source_id, service.analyze_saved(source_id, news_id), response)


async def _created_analysis(source_id, operation, response=None):
    try:
        saved = await operation
    except CompanyContextExternalTransferBlocked as error:
        raise HTTPException(503, detail={'code':'COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED',
            'message':'Передача контекста БД внешнему AI не разрешена.'}) from error
    except AnalysisConflict as error:
        detail = {'code':error.code,'message':'Анализ не запущен: требуется ожидание или административная проверка.'}
        if error.run_id is not None:
            detail['run_id'] = error.run_id
        raise HTTPException(409, detail=detail) from error
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
    if response is not None and getattr(saved, 'reused', False):
        response.status_code = 200
    if getattr(saved, 'cached_response', None) is not None:
        return saved.cached_response
    return CreatedCompanyAnalysis(
        run_id=saved.run_id, insight_id=saved.insight_id, news_id=saved.news_id,
        company_id=source_id, analysis=saved.result.analysis,
    )
