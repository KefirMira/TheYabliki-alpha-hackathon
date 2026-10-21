
from typing import Literal

from pydantic import BaseModel, Field


class AnalysisContent(BaseModel):
    relevance: Literal["high", "medium", "low", "unknown"]
    summary: str = Field(min_length=1)

    risks: list[str]
    opportunities: list[str]
    recommendations: list[str]


class ValidationResult(BaseModel):
    passed: bool
    warnings: list[str]


class AnalysisSource(BaseModel):
    id: int
    document: str
    page: int
    score: float


class CompanyAnalysisResponse(BaseModel):
    company_id: str
    news: str

    relevance: Literal["high", "medium", "low", "unknown"]
    summary: str

    risks: list[str]
    opportunities: list[str]
    recommendations: list[str]

    sources: list[AnalysisSource]
    validation: ValidationResult
