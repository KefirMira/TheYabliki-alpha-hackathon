
from pydantic import BaseModel, Field, PrivateAttr


class CompanyProfile(BaseModel):
    # Server-only metadata: never accepted/serialized as an HTTP field.
    _ai_context: dict | None = PrivateAttr(default=None)

    company_id: str

    industry: str | None = None
    region: str | None = None

    revenue: float | None = Field(default=None, ge=0)
    credit_exposure: float | None = Field(default=None, ge=0)
