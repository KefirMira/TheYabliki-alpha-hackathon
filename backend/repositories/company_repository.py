"""Read-only projection of the existing companies table; no ORM table creation."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import BigInteger, Integer, Numeric, String, column, select, table
from sqlalchemy.ext.asyncio import AsyncSession


companies = table(
    "companies",
    column("id", BigInteger),
    column("source_id", String),
    column("name", String),
    column("industry", String),
    column("region", String),
    column("revenue", Numeric(18, 2)),
    column("revenue_year", Integer),
    column("client_status", String),
    schema="public",
)


@dataclass(frozen=True)
class CompanyRecord:
    id: int
    source_id: str
    name: str
    industry: str | None
    region: str | None
    revenue: Decimal | None
    revenue_year: int | None
    client_status: str | None


class CompanyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_source_id(self, source_id: str) -> CompanyRecord | None:
        result = await self.session.execute(
            select(companies).where(companies.c.source_id == source_id)
        )
        row = result.mappings().one_or_none()
        return CompanyRecord(**row) if row is not None else None
