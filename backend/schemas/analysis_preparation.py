"""Internal local-only preparation report, not a public analysis API contract."""
from typing import Literal

from pydantic import BaseModel, Field

from schemas.persisted_analysis import PersistableAnalysis
from schemas.preparation_diagnostics import PreparationDiagnostic


class PreparationStep(BaseModel):
    tool: str
    purpose: str
    required_data: list[str]
    status: Literal['PENDING', 'RUNNING', 'OK', 'BLOCKED', 'FAILED', 'SKIPPED'] = 'PENDING'
    input_sha256: str | None = None
    output_sha256: str | None = None
    result: dict = Field(default_factory=dict)


class AnalysisPreparation(BaseModel):
    version: Literal['analysis-preparation-v1'] = 'analysis-preparation-v1'
    trace_id: str
    status: Literal['PLANNED', 'PREPARED_LOCAL', 'INCOMPLETE', 'FAILED'] = 'PLANNED'
    steps: list[PreparationStep]
    prepared_input: dict | None = None
    local_stub_result: PersistableAnalysis | None = None
    external_transfer_allowed: Literal[False] = False
    paid_calls: Literal[0] = 0
    error_code: str | None = None
    diagnostic: PreparationDiagnostic | None = None
    human_review_required: Literal[True] = True
