"""Internal, isolated-fixture-only entry point. No endpoint or automatic gateway enablement."""
import asyncio
import copy
from schemas.orchestration import GatewayOrchestrationTrace
from schemas.synthetic_execution import SyntheticGatewayExecution
from services.synthetic_news_execution_service import SyntheticNewsExecutionService, LocalExecutionStopped, EXECUTION_PLAN
from services.synthetic_gateway_input import fixture, evidence_ids, make_input
from services.synthetic_draft_adapter import SyntheticDraftAdapter, MODEL


class SyntheticGatewayExecutionService(SyntheticNewsExecutionService):
    report_type = SyntheticGatewayExecution
    trace_type = GatewayOrchestrationTrace
    prompt_version = 'synthetic-gateway-v1'
    mode_warning = 'SYNTHETIC_GATEWAY_ANALYSIS_NOT_FOR_DECISIONS'
    draft_reason = 'SYNTHETIC_SDK_COMPLETED'
    execution_plan = tuple(('synthetic_draft','One bounded synthetic SDK draft',['approved_fixture']) if tool=='fake_llm'
                          else (tool,purpose,needs) for tool,purpose,needs in EXECUTION_PLAN)

    def __init__(self, sessions, *, draft_adapter, session_token):
        if type(draft_adapter) is not SyntheticDraftAdapter:
            raise ValueError('BOUNDED_DRAFT_ADAPTER_REQUIRED')
        self.adapter=draft_adapter
        super().__init__(sessions,corpus_loader=lambda:copy.deepcopy(fixture()['corpus']),
            confirm_synthetic=True,session_token=session_token)
        self.model_name=MODEL if self.adapter.transport=='organizer' else 'fake-synthetic-gateway-v1'

    def _check_target(self, source_id):
        super()._check_target(source_id)
        if source_id!=fixture()['source_id']:
            raise LocalExecutionStopped('SYNTHETIC_FIXTURE_TARGET_REQUIRED')

    def record_preparation(self, report, preparation):
        # The old preparation includes a DB snapshot: never include it in the gateway report.
        pass

    def prepare_payload(self, payload, source_id):
        data=fixture()
        if source_id!=data['source_id'] or payload['news_from_db']['content']!=data['news']:
            raise LocalExecutionStopped('SYNTHETIC_FIXTURE_SNAPSHOT_MISMATCH')
        evidence_ids(payload['analytical_source_assertions'])
        # Locally review/plan against the same approved fixture facts that the model receives.
        # Do not remove company._ai_context or alter the ordinary transfer guard.
        payload['company_source_assertions']=copy.deepcopy(data['context'])
        return payload

    async def draft(self, payload, report):
        if self.adapter.requests:
            raise LocalExecutionStopped('GATEWAY_REQUEST_LIMIT')
        dto=make_input(evidence_ids(payload['analytical_source_assertions']))
        trace=report.orchestration
        trace.transport=self.adapter.transport
        try:
            return await self.adapter.complete(dto)
        finally:
            trace.sdk_requests=self.adapter.requests
            trace.paid_calls=self.adapter.requests if self.adapter.transport=='organizer' else 0
            report.paid_calls=trace.paid_calls
            trace.outbound_sha256=self.adapter.outbound_sha256
            trace.usage=copy.deepcopy(self.adapter.usage)
            trace.finish_reason=self.adapter.finish_reason
            trace.request_outcome=self.adapter.outcome
            trace.elapsed_ms=self.adapter.elapsed_ms

    async def analyze_saved(self, source_id, news_id):
        try:
            async with asyncio.timeout(120):
                report=await super().analyze_saved(source_id,news_id)
                if report.orchestration is not None:
                    report.orchestration.error_code=report.error_code
                return report
        except TimeoutError:
            # Existing CompanyAnalysisService handles cancellation/failure status conservatively.
            # No SDK retry and no assertion that provider execution/charging stopped.
            return SyntheticGatewayExecution(status='UNCERTAIN',steps=[],error_code='GATEWAY_TOTAL_TIMEOUT_UNKNOWN')
