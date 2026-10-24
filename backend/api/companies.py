from api.auth import company_read, current_actor, AUTH_ERRORS
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_company_session
from repositories.company_repository import CompanyRepository
from schemas.company_api import CompanyProfileResponse
from schemas.http_docs import errors
from services.company_profile_service import CompanyNotFound, CompanyProfileService


router = APIRouter(prefix="/api/companies", tags=["companies"], dependencies=[Depends(company_read)], responses=AUTH_ERRORS)


@router.get("/{source_id}", response_model=CompanyProfileResponse, responses=errors(**{"404": "COMPANY_NOT_FOUND", "503": "DATABASE_UNAVAILABLE"}),
    description="Поиск companies.source_id. Денежные Decimal возвращаются строками; credit_exposure=None, технический ID не является названием.")
async def get_company(
    source_id: str = Path(min_length=1, max_length=200),
    session: AsyncSession = Depends(get_company_session),
):
    service = CompanyProfileService(CompanyRepository(session))
    try:
        return await service.get_frontend_profile(source_id)
    except CompanyNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "COMPANY_NOT_FOUND", "message": "Компания не найдена"},
        ) from error
