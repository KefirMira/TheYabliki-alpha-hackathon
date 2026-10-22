from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel


class InsightFeedItem(BaseModel):
    insight_id: int
    run_id: int
    company_id: str
    type: Literal["risk", "opportunity", "mixed", "information"] | None
    relevance: Literal["high", "medium", "low", "unknown"] | None
    summary: str | None
    created_at: datetime
    status: Literal["COMPLETED"]


class InsightFeed(BaseModel):
    items: list[InsightFeedItem]
    next_cursor: str | None = None


class InsightNews(BaseModel):
    id: int
    title: str
    text: str | None


class InsightEvidence(BaseModel):
    id: int
    evidence_type: str
    text: str
    document: str | None
    page: int | None
    chunk_id: int | None
    document_date: date | None


class InsightCard(InsightFeedItem):
    news: InsightNews
    risks: list[str]
    opportunities: list[str]
    recommendations: list[str]
    validation: dict[str, Any]
    # Preserve the stored source metadata, including dates of partial precision.
    sources: list[dict[str, Any]]
    evidence: list[InsightEvidence]
