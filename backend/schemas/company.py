
from pydantic import BaseModel, Field


class CompanyProfile(BaseModel):
    company_id: str

    industry: str | None = None
    region: str | None = None

    revenue: float | None = Field(default=None, ge=0)
    credit_exposure: float | None = Field(default=None, ge=0)
