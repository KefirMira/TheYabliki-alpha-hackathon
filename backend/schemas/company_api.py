from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_serializer


class CompanyProfileResponse(BaseModel):
    company_id: str
    name: str | None
    name_is_placeholder: bool
    industry: str | None
    region: str | None
    revenue: Decimal | None = Field(ge=0)
    revenue_year: int | None
    client_status: Literal["CLIENT", "PROSPECT", "CLOSED_CLIENT"] | None
    credit_exposure: None = None

    @field_serializer("revenue", when_used="json")
    def serialize_revenue(self, value: Decimal | None) -> str | None:
        # Money travels as a decimal string, never an IEEE-754 JSON number.
        return format(value, "f") if value is not None else None
