"""Internal fake-only adapter over existing saved-news jobs and atomic persistence."""
import copy
import json
import re
from fastapi import HTTPException
from pydantic import SecretStr
from services.auth_service import AuthService, unauthorized
from services.local_adaptive_service import LocalAdaptiveAgent, AgentStopped, fake_decision
from schemas.orchestration import OrchestrationTrace

from schemas.analysis import ValidationResult
from schemas.analysis_preparation import PreparationStep
from schemas.company_analysis_api import CreatedCompanyAnalysis
from schemas.synthetic_execution import SyntheticExecution
from services.analysis_preparation_service import AnalysisPreparationService, digest
from services.company_analysis_service import (
    CompanyAnalysisService, AnalysisFailure, RunStatusUncertain,
    NewsNotFound, NewsNotAnalyzable,
)
from services.company_profile_service import CompanyNotFound
from services.personalization_service import analyze_for_company_with_evidence
from services.protected_ai import protected_call
from services.financial_review_service import review_financial_analysis
from repositories.news_analysis_job_repository import AnalysisConflict
from repositories.evidence_repository import EvidenceRepository

FAKE_MODEL = 'local-fake-orchestration-v1'
EXECUTION_PLAN = (
    ('claim', 'Existing claim/dispatch or COMPLETED cache', ['company_id', 'news_id']),
    ('preparation', 'Existing read-only local preparation', ['saved_news', 'company_context']),
    ('fake_llm', 'One local fake SDK call, no provider', ['prepared_input']),
    ('validate_result', 'Existing JSON/evidence contract plus exact provenance', ['fake_response', 'prepared_evidence']),
    ('financial_review', 'Deterministic financial review, never a truth certificate', ['analysis', 'company_context', 'evidence']),
    ('persist', 'Existing fenced atomic insight/evidence/payload/COMPLETED commit', ['validated_bundle', 'claim_token']),
)


class LocalFakeAnalysisSDK:
    """No HTTP, credentials, imports of provider SDK, retries or configuration."""
    async def decide(self, observation):
        return fake_decision(observation)

    async def complete(self, prepared_input):
        return json.dumps({'relevance': 'unknown',
            'summary': 'Синтетический fake-анализ конвейера; модельные выводы не получены.',
            'risks': [], 'opportunities': [], 'recommendations': []}, ensure_ascii=False)


class LocalExecutionStopped(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class SyntheticNewsExecutionService:
    """Test-database-only entry point; no endpoint/CLI or production service registration."""
    def __init__(self, sessions, *, corpus_loader, confirm_synthetic=False,
                 fake_sdk=None, evidence_repository=EvidenceRepository, session_token=None):
        if session_token is not None and not isinstance(session_token,str):
            raise ValueError('SESSION_TOKEN_STRING_REQUIRED')
        self.session_token = SecretStr(session_token) if session_token else None
        self.sessions = sessions
        self.corpus_loader = corpus_loader
        self.confirm_synthetic = confirm_synthetic
        self.fake_sdk = fake_sdk if fake_sdk is not None else LocalFakeAnalysisSDK()
        if type(self.fake_sdk) is not LocalFakeAnalysisSDK:
            raise ValueError('LOCAL_FAKE_SDK_REQUIRED')
        self.evidence_repository = evidence_repository

    report_type = SyntheticExecution
    trace_type = OrchestrationTrace
    model_name = FAKE_MODEL
    prompt_version = 'local-adaptive-v1'
    mode_warning = 'SYNTHETIC_FAKE_ANALYSIS_NOT_FOR_DECISIONS'
    draft_reason = 'LOCAL_FAKE_COMPLETED'
    execution_plan = EXECUTION_PLAN

    def record_preparation(self, report, preparation):
        report.preparation = preparation

    def prepare_payload(self, payload, source_id):
        return payload

    async def draft(self, payload, report):
        if report.fake_calls:
            raise LocalExecutionStopped('LOCAL_FAKE_ALREADY_CALLED')
        report.fake_calls += 1
        return await self.fake_sdk.complete(copy.deepcopy(payload))

    def _check_target(self, source_id):
        engine = self.sessions.kw.get('bind')
        url = getattr(engine, 'url', None)
        # Reuse the existing isolated_database namespace; never a demo/import/shared DB.
        if (self.confirm_synthetic is not True or not isinstance(source_id, str) or not source_id.startswith('SYNTH-')
                or url is None or url.drivername != 'postgresql+asyncpg'
                or url.host not in {'127.0.0.1', '::1'}
                or not re.fullmatch(r'test_news_identity_[0-9a-f]{32}', url.database or '')):
            raise LocalExecutionStopped('SYNTHETIC_ISOLATED_TARGET_REQUIRED')

    async def analyze_saved(self, source_id, news_id):
        # All per-execution state is local, even when this service handles concurrent calls.
        report = self.report_type(status='FAILED', steps=[
            PreparationStep(tool=tool, purpose=purpose, required_data=needs)
            for tool, purpose, needs in self.execution_plan])
        active = report.steps[0]
        safe_error = None
        agent = None

        def start(index, inputs):
            nonlocal active
            active = report.steps[index]
            active.status = 'RUNNING'
            active.input_sha256 = digest(inputs)

        def finish(value, summary):
            active.output_sha256 = digest(value)
            active.result = summary
            active.status = 'OK'

        async def analyzer(*, news, company):
            nonlocal safe_error, agent
            try:
                if not protected_call.get():
                    raise LocalExecutionStopped('EXISTING_JOB_DISPATCH_REQUIRED')
                finish({'claimed': True}, {'existing_job_dispatch': True})
                start(1, {'company_id': source_id, 'news_id': news_id})
                report.orchestration = self.trace_type()
                agent = LocalAdaptiveAgent(self.fake_sdk, report.orchestration)
                agent.log('PREPARE','LOCAL_SNAPSHOT')
                corpus = copy.deepcopy(self.corpus_loader())
                preparation = await AnalysisPreparationService(
                    self.sessions, corpus_loader=lambda: corpus).prepare(source_id, news_id)
                self.record_preparation(report, preparation)
                if preparation.status != 'PREPARED_LOCAL' or preparation.prepared_input is None:
                    if preparation.error_code == 'NO_RAG_CONTEXT':
                        from schemas.orchestration import Observation
                        await agent.decide(Observation(stage='evidence',missing_context=0,context_partial=True,source_count=0))
                    raise LocalExecutionStopped(preparation.error_code or 'LOCAL_PREPARATION_FAILED')
                payload = copy.deepcopy(preparation.prepared_input)
                if (payload['news_from_db']['content'] != news
                        or digest(payload['company_source_assertions']) != digest(company._ai_context)):
                    raise LocalExecutionStopped('CLAIM_PREPARATION_SNAPSHOT_CHANGED')
                expected = copy.deepcopy(payload['analytical_source_assertions'])
                if [fragment.model_dump() for fragment in preparation.local_stub_result.evidence] != expected:
                    raise LocalExecutionStopped('PREPARATION_EVIDENCE_MISMATCH')
                payload = self.prepare_payload(payload, source_id)
                await agent.select_evidence(payload, corpus)
                expected = copy.deepcopy(payload['analytical_source_assertions'])
                finish(payload, {'trace_id': preparation.trace_id, 'external_transfer_allowed': False})

                raw_response = None
                async def local_rag(*, question, search_query, include_evidence):
                    nonlocal raw_response
                    if question != payload['question'] or search_query != news or include_evidence is not True:
                        raise LocalExecutionStopped('LOCAL_INPUT_MISMATCH')
                    start(2, {'input_sha256': digest(payload)})
                    report.orchestration.drafts += 1
                    raw = await self.draft(payload, report)
                    raw_response = raw
                    agent.log('DRAFT',self.draft_reason,after_sha256=digest(raw))
                    finish(raw, {'engine': self.model_name, 'paid_calls': report.paid_calls})
                    start(3, {'response_sha256': digest(raw), 'evidence_sha256': digest(expected)})
                    return {'analysis': raw, 'sources': [{key: item[key] for key in ('id', 'document', 'page', 'score')}
                                                       for item in expected],
                            'evidence': copy.deepcopy(expected), 'model_name': self.model_name}

                # Existing parsing, validation, response assembly; no duplicate persistence logic.
                bundle = await analyze_for_company_with_evidence(news, company, _local_rag=local_rag)
                if ([item.model_dump() for item in bundle.evidence] != expected
                        or bundle.analysis.company_id != source_id or bundle.analysis.news != news):
                    raise LocalExecutionStopped('LOCAL_RESULT_PROVENANCE_MISMATCH')
                finish(bundle.model_dump(mode='json'), {'schema_valid': True, 'exact_evidence': True})
                start(4, {'analysis_sha256': digest(bundle.analysis.model_dump(mode='json')),
                          'context_sha256': digest(payload['company_source_assertions']),
                          'evidence_sha256': digest(expected)})
                async def reassemble(raw):
                    async def replay(*, question, search_query, include_evidence):
                        if question != payload['question'] or search_query != news or include_evidence is not True:
                            raise LocalExecutionStopped('LOCAL_INPUT_MISMATCH')
                        return {'analysis':raw, 'sources':[{k:e[k] for k in ('id','document','page','score')} for e in expected],
                                'evidence':copy.deepcopy(expected), 'model_name':self.model_name}
                    return await analyze_for_company_with_evidence(news,company,_local_rag=replay)
                bundle, review = await agent.check_and_correct(bundle,raw_response,payload,review_financial_analysis,reassemble)
                report.financial_review = review
                if review.blocking:
                    raise LocalExecutionStopped('FINANCIAL_REVIEW_BLOCKED')
                bundle.financial_review = review
                bundle.orchestration = report.orchestration.checked()
                bundle.analysis.validation = ValidationResult(passed=False, warnings=list(dict.fromkeys([
                    *bundle.analysis.validation.warnings,
                    self.mode_warning, 'FACTUAL_ACCURACY_NOT_ASSESSED',
                    'FINANCIAL_CORRECTNESS_NOT_ESTABLISHED',
                    *[finding.code for finding in review.findings]])))
                bundle.prompt_version = self.prompt_version
                finish(bundle.model_dump(mode='json'), {'schema_valid': True, 'exact_evidence': True,
                    'factual_accuracy': 'NOT_ASSESSED', 'human_review_required': True})
                start(5, {'validated_bundle_sha256': digest(bundle.model_dump(mode='json'))})
                return bundle
            except Exception as error:
                if agent is not None:
                    report.financial_review = agent.last_review
                safe_error = error.code if isinstance(error, (LocalExecutionStopped,AgentStopped)) else 'LOCAL_EXECUTION_FAILED'
                raise

        try:
            self._check_target(source_id)
            if isinstance(news_id,bool) or not isinstance(news_id,int) or not 0 < news_id < 2**63:
                raise LocalExecutionStopped('INVALID_NEWS_ID')
            if self.session_token is None:
                raise unauthorized()
            actor = await AuthService(self.sessions).authenticate(self.session_token.get_secret_value())
            start(0, {'source_id': source_id, 'news_id': news_id})
            saved = await CompanyAnalysisService(self.sessions, analyzer=analyzer,
                evidence_repository=self.evidence_repository,actor_id=actor.user_id).analyze_saved(source_id, news_id)
            result = saved.cached_response or CreatedCompanyAnalysis(run_id=saved.run_id,
                insight_id=saved.insight_id, news_id=saved.news_id, company_id=source_id,
                analysis=saved.result.analysis)
            report.run_id = saved.run_id
            report.result = result
            report.status = 'REUSED' if saved.reused else 'COMPLETED'
            if not saved.reused and report.orchestration is not None:
                report.orchestration = report.orchestration.committed()
            finish(result.model_dump(mode='json'), {'run_id': saved.run_id, 'insight_id': saved.insight_id,
                'reused': saved.reused, 'existing_atomic_commit': not saved.reused})
        except LocalExecutionStopped as error:
            report.status, report.error_code = 'REJECTED', error.code
        except HTTPException as error:
            report.status, report.error_code = 'REJECTED', error.detail['code']
        except AnalysisConflict as error:
            report.status, report.error_code, report.run_id = 'CONFLICT', error.code, error.run_id
        except RunStatusUncertain as error:
            report.status, report.error_code, report.run_id = 'UNCERTAIN', error.code, error.run_id
        except AnalysisFailure as error:
            report.status, report.error_code, report.run_id = 'FAILED', safe_error or error.code, error.run_id
        except (CompanyNotFound, NewsNotFound, NewsNotAnalyzable) as error:
            report.error_code = {CompanyNotFound: 'COMPANY_NOT_FOUND', NewsNotFound: 'NEWS_NOT_FOUND',
                                 NewsNotAnalyzable: 'NEWS_NOT_ANALYZABLE'}[type(error)]
        except Exception:
            report.status, report.error_code = 'UNCERTAIN', 'LOCAL_STATUS_UNCERTAIN'
        finally:
            if report.error_code:
                if report.orchestration is not None:
                    report.orchestration.status = 'FAILED'
                active.status = 'FAILED'
                active.result = {'code': report.error_code}
            for step in report.steps:
                if step.status == 'PENDING':
                    step.status = 'SKIPPED'
        return report
