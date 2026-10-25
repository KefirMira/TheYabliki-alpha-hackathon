"""Operation-level advice, never an authorization token or a job-state projection."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CapabilityReason(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal["ACCESS", "MODE", "DATA_POLICY", "REQUEST", "IMPLEMENTATION", "PROVIDER"]
    code: Literal[
        "ANALYSIS_PERMISSION_REQUIRED", "AI_DISABLED_IN_DEMO",
        "COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED", "NEWS_AND_JOB_NOT_EVALUATED",
        "EXECUTION_PREREQUISITES_NOT_EVALUATED", "ADMINISTRATIVE_RETRY_ONLY",
        "PROVIDER_NOT_PROBED",
    ]


class OperationCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: Literal["AVAILABLE", "BLOCKED", "UNAVAILABLE", "UNKNOWN"] = Field(
        description="AVAILABLE: обработчик разрешён при перечисленных условиях, не гарантия результата. "
        "BLOCKED: известен запрет. UNAVAILABLE: нет публичной операции. UNKNOWN: данных для решения недостаточно.")
    reasons: list[CapabilityReason] = Field(default_factory=list)
    conditions: list[Literal[
        "REQUEST_VALIDATION_REQUIRED", "NEWS_GRANT_REQUIRED", "VISIBLE_COMPLETED_INSIGHTS_ONLY",
        "DEMO_SYNTHETIC_NEWS_ONLY", "COMPLETED_RESULT_REQUIRED",
        "EXISTING_JOB_AND_RETRY_POLICY_APPLY",
    ]] = Field(default_factory=list)


class CompanyOperations(BaseModel):
    model_config = ConfigDict(extra="forbid")
    read_profile: OperationCapability
    read_insights: OperationCapability
    submit_news: OperationCapability
    analyze_new: OperationCapability
    reuse_completed: OperationCapability
    retry_analysis: OperationCapability


class ProviderCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: Literal["UNKNOWN"] = "UNKNOWN"
    reason: CapabilityReason = Field(default_factory=lambda: CapabilityReason(
        category="PROVIDER", code="PROVIDER_NOT_PROBED"))


class CompanyCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_id: str = Field(description="Запрошенный companies.source_id, только после проверки membership.")
    mode: Literal["demo", "full"]
    dataset_analysis: OperationCapability | None = None
    dataset_transport: Literal["fake","organizer"] | None = None
    operations: CompanyOperations
    external_provider: ProviderCapability = Field(default_factory=ProviderCapability)
