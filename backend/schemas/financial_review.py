"""Review observations, not a financial correctness certificate."""
from typing import Literal

from pydantic import BaseModel, Field


class FinancialFinding(BaseModel):
    code: str
    severity: Literal['INFO', 'WARNING', 'ERROR']
    disposition: Literal['UNKNOWN', 'NEEDS_REVIEW', 'CONFIRMED_ERROR']
    field: str
    claim: str = Field(max_length=1200)
    claim_truncated: bool = False
    explanation: str
    source_ids: list[int] = Field(default_factory=list)


class FinancialReview(BaseModel):
    version: Literal['financial-review-v1'] = 'financial-review-v1'
    status: Literal['UNKNOWN', 'NEEDS_REVIEW', 'ERROR']
    findings: list[FinancialFinding]
    blocking: bool = False
    coverage_complete: bool = True
    financial_correctness: Literal['UNKNOWN'] = 'UNKNOWN'
    human_review_required: Literal[True] = True
