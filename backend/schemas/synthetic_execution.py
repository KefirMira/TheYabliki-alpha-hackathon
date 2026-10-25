"""Private synthetic test report; never a replacement for the production API."""
from typing import Literal

from pydantic import BaseModel

from schemas.analysis_preparation import AnalysisPreparation, PreparationStep
from schemas.company_analysis_api import CreatedCompanyAnalysis
from schemas.financial_review import FinancialReview
from schemas.orchestration import OrchestrationTrace, GatewayOrchestrationTrace


class SyntheticExecution(BaseModel):
    mode: Literal['synthetic-fake-only'] = 'synthetic-fake-only'
    status: Literal['COMPLETED', 'REUSED', 'CONFLICT', 'FAILED', 'UNCERTAIN', 'REJECTED']
    steps: list[PreparationStep]
    preparation: AnalysisPreparation | None = None
    financial_review: FinancialReview | None = None
    orchestration: OrchestrationTrace | None = None
    result: CreatedCompanyAnalysis | None = None
    run_id: int | None = None
    error_code: str | None = None
    fake_calls: int = 0
    paid_calls: Literal[0] = 0
    factual_accuracy: Literal['NOT_ASSESSED'] = 'NOT_ASSESSED'
    human_review_required: Literal[True] = True


class SyntheticGatewayExecution(SyntheticExecution):
    mode: Literal['synthetic-gateway-only'] = 'synthetic-gateway-only'
    orchestration: GatewayOrchestrationTrace | None = None
    paid_calls: int = 0
