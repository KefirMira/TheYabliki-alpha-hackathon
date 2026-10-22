from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_company_session
from repositories.company_repository import CompanyRepository
from schemas.company_api import CompanyProfileResponse
from services.company_profile_service import CompanyNotFound, CompanyProfileService


router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("/{source_id}", response_model=CompanyProfileResponse)
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
