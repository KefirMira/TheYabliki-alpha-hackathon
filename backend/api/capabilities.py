"""Company-scoped, advisory and read-only; execution always rechecks its own ACL."""
from fastapi import APIRouter, Depends, Path
from sqlalchemy.exc import SQLAlchemyError

from api.auth import AUTH_ERRORS, company_read
from db.session import get_company_session, unavailable
from schemas.capabilities import CompanyCapabilities
from services.capabilities_service import CompanyCapabilitiesService


router = APIRouter(prefix="/api/companies", tags=["capabilities"], responses=AUTH_ERRORS)


@router.get("/{source_id}/capabilities", response_model=CompanyCapabilities,
            description="Текущая сессия и membership обязательны. Read-only описание операций, без LLM, "
            "RAG, чтения новостей/jobs и создания заданий. AVAILABLE не гарантирует наличие результата: "
            "действуют conditions. UNKNOWN для непроверенных news grant/job и провайдера. "
            "Demo запрещает и новый AI, и POST COMPLETED cache; full не снимает запрет передачи DB-контекста. "
            "Не выдаёт прав, токенов или разрешения retry; каждый целевой endpoint заново проверяет ACL.")
async def company_capabilities(
    source_id: str = Path(min_length=1, max_length=200),
    actor=Depends(company_read),
    session=Depends(get_company_session),
):
    try:
        return await CompanyCapabilitiesService(session).get(source_id, actor.user_id)
    except (SQLAlchemyError, OSError, TimeoutError):
        raise unavailable() from None
