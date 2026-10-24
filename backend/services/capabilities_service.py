"""No news/job scans, context loading, configuration disclosure or provider probes."""
from repositories.auth_repository import AuthRepository
from schemas.capabilities import CapabilityReason, CompanyCapabilities, CompanyOperations, OperationCapability
from services.auth_service import denied
from services.company_context_service import CompanyContextExternalTransferBlocked, external_transfer_guard
from settings import ai_disabled_reason, execution_mode


def operation(state, *, reasons=(), conditions=()):
    return OperationCapability(state=state, reasons=list(reasons), conditions=list(conditions))


def describe_capabilities(source_id, *, can_analyze):
    mode = execution_mode()
    analysis_blocks = []
    if not can_analyze:
        analysis_blocks.append(CapabilityReason(category="ACCESS", code="ANALYSIS_PERMISSION_REQUIRED"))
    mode_reason = ai_disabled_reason()
    if mode_reason:
        analysis_blocks.append(CapabilityReason(category="MODE", code=mode_reason))
    # Saved-company analysis always prepares a non-None DB context before AI.
    # Probe that existing guard using an empty marker; never load real context.
    new_blocks = list(analysis_blocks)
    try:
        external_transfer_guard({})
    except CompanyContextExternalTransferBlocked:
        new_blocks.append(CapabilityReason(category="DATA_POLICY", code="COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED"))
    new_unknown = CapabilityReason(category="REQUEST", code="EXECUTION_PREREQUISITES_NOT_EVALUATED")
    cached_unknown = CapabilityReason(category="REQUEST", code="NEWS_AND_JOB_NOT_EVALUATED")
    return CompanyCapabilities(company_id=source_id, mode=mode, operations=CompanyOperations(
        read_profile=operation("AVAILABLE"),
        read_insights=operation("AVAILABLE", conditions=("NEWS_GRANT_REQUIRED", "VISIBLE_COMPLETED_INSIGHTS_ONLY")),
        submit_news=operation("AVAILABLE", conditions=("REQUEST_VALIDATION_REQUIRED",) +
                              (("DEMO_SYNTHETIC_NEWS_ONLY",) if mode_reason else ())),
        analyze_new=operation("BLOCKED" if new_blocks else "UNKNOWN",
                              reasons=new_blocks or [new_unknown],
                              conditions=("REQUEST_VALIDATION_REQUIRED", "NEWS_GRANT_REQUIRED", "EXISTING_JOB_AND_RETRY_POLICY_APPLY")),
        reuse_completed=operation("BLOCKED" if analysis_blocks else "UNKNOWN",
                                 reasons=analysis_blocks or [cached_unknown],
                                 conditions=("NEWS_GRANT_REQUIRED", "COMPLETED_RESULT_REQUIRED", "EXISTING_JOB_AND_RETRY_POLICY_APPLY")),
        retry_analysis=operation("UNAVAILABLE", reasons=[CapabilityReason(
            category="IMPLEMENTATION", code="ADMINISTRATIVE_RETRY_ONLY")],
            conditions=("EXISTING_JOB_AND_RETRY_POLICY_APPLY",)),
    ))


class CompanyCapabilitiesService:
    def __init__(self, session):
        self.auth = AuthRepository(session)

    async def get(self, source_id, user_id):
        # Reuse the same ACL repository as execution; safe for internal callers too.
        if not await self.auth.company_allowed(user_id, source_id):
            raise denied()
        can_analyze = await self.auth.company_allowed(user_id, source_id, True)
        return describe_capabilities(source_id, can_analyze=can_analyze)
