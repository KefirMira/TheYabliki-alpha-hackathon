from repositories.company_repository import CompanyRecord, CompanyRepository
from schemas.company import CompanyProfile
from schemas.company_api import CompanyProfileResponse


class CompanyNotFound(Exception):
    pass


def to_company_profile(record: CompanyRecord) -> CompanyProfile:
    """Compatibility adapter: legacy AI expects float; database/API keep Decimal."""
    return CompanyProfile(
        company_id=record.source_id,
        industry=record.industry,
        region=record.region,
        revenue=float(record.revenue) if record.revenue is not None else None,
        credit_exposure=None,
    )


def to_profile_response(record: CompanyRecord) -> CompanyProfileResponse:
    name = record.name.strip()
    placeholder = not name or name == record.source_id.strip()
    return CompanyProfileResponse(
        company_id=record.source_id,
        name=None if placeholder else name,
        name_is_placeholder=placeholder,
        industry=record.industry,
        region=record.region,
        revenue=record.revenue,
        revenue_year=record.revenue_year,
        client_status=record.client_status,
        credit_exposure=None,
    )


class CompanyProfileService:
    def __init__(self, repository: CompanyRepository):
        self.repository = repository

    async def get_record(self, source_id: str) -> CompanyRecord:
        record = await self.repository.get_by_source_id(source_id)
        if record is None:
            raise CompanyNotFound(source_id)
        return record

    async def get_profile(self, source_id: str) -> CompanyProfile:
        return to_company_profile(await self.get_record(source_id))

    async def get_frontend_profile(self, source_id: str) -> CompanyProfileResponse:
        return to_profile_response(await self.get_record(source_id))
