from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.analysis import CompanyAnalysisResponse


class ManualNewsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=100_000)
    title: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("text", "title")
    @classmethod
    def not_blank(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Text must not be blank")
        return value  # Preserve the exact news text, including line breaks.


class CompanyAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    news: ManualNewsInput


class CreatedCompanyAnalysis(BaseModel):
    run_id: int = Field(gt=0)
    insight_id: int = Field(gt=0)
    news_id: int = Field(gt=0)
    status: Literal["COMPLETED"] = "COMPLETED"
    company_id: str
    analysis: CompanyAnalysisResponse
