from api.auth import company_read, current_actor, AUTH_ERRORS
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.exc import SQLAlchemyError

from db.session import get_company_session, unavailable
from schemas.insights import InsightCard, InsightFeed
from schemas.http_docs import errors
from services.company_profile_service import CompanyNotFound
from services.insight_cursor import InvalidInsightCursor, decode_cursor
from services.insight_service import InsightNotFound, InsightService


router = APIRouter(prefix="/api/companies", tags=["insights"], dependencies=[Depends(company_read)], responses=AUTH_ERRORS)


def get_insight_service(session=Depends(get_company_session), actor=Depends(current_actor)):
    return InsightService(session, actor_id=actor.user_id)


def get_cursor(source_id: str = Path(min_length=1, max_length=200), cursor: str | None = Query(default=None, max_length=2048)):
    try:
        return decode_cursor(cursor, source_id)
    except InvalidInsightCursor as error:
        raise HTTPException(422, detail={"code": "INVALID_CURSOR", "message": "Некорректный курсор"}) from error


def read_error(error):
    if isinstance(error, CompanyNotFound):
        return HTTPException(404, detail={"code": "COMPANY_NOT_FOUND", "message": "Компания не найдена"})
    if isinstance(error, InsightNotFound):
        return HTTPException(404, detail={"code": "INSIGHT_NOT_FOUND", "message": "Инсайт не найден"})
    return unavailable()


@router.get("/{source_id}/insights", response_model=InsightFeed, responses=errors(**{"404": "COMPANY_NOT_FOUND", "422": "Валидация или INVALID_CURSOR", "503": "DATABASE_UNAVAILABLE"}),
    description="Только COMPLETED; created_at DESC, id DESC. limit 1–100 (default 20), курсор привязан к компании. Пустая история: 200.")
async def list_insights(
    source_id: str = Path(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    position=Depends(get_cursor),
    service: InsightService = Depends(get_insight_service),
):
    try:
        return await service.list(source_id, limit, position)
    except (CompanyNotFound, SQLAlchemyError, OSError, TimeoutError) as error:
        raise read_error(error) from error


@router.get("/{source_id}/insights/{insight_id}", response_model=InsightCard, responses=errors(**{"404": "COMPANY_NOT_FOUND / INSIGHT_NOT_FOUND, включая чужой инсайт", "503": "DATABASE_UNAVAILABLE"}),
    description="Сохранённый COMPLETED результат и evidence запрошенной компании; без LLM.")
async def get_insight(
    source_id: str = Path(min_length=1, max_length=200),
    insight_id: int = Path(gt=0, le=9223372036854775807),
    service: InsightService = Depends(get_insight_service),
):
    try:
        return await service.card(source_id, insight_id)
    except (CompanyNotFound, InsightNotFound, SQLAlchemyError, OSError, TimeoutError) as error:
        raise read_error(error) from error
