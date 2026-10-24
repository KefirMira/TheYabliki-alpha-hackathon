"""Internal fake-only adapter over existing saved-news jobs and atomic persistence."""
import copy
import json
import re

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
from repositories.news_analysis_job_repository import AnalysisConflict
from repositories.evidence_repository import EvidenceRepository

FAKE_MODEL = 'local-fake-orchestration-v1'
EXECUTION_PLAN = (
    ('claim', 'Existing claim/dispatch or COMPLETED cache', ['company_id', 'news_id']),
    ('preparation', 'Existing read-only local preparation', ['saved_news', 'company_context']),
    ('fake_llm', 'One local fake SDK call, no provider', ['prepared_input']),
    ('validate_result', 'Existing JSON/evidence contract plus exact provenance', ['fake_response', 'prepared_evidence']),
    ('persist', 'Existing fenced atomic insight/evidence/payload/COMPLETED commit', ['validated_bundle', 'claim_token']),
)


class LocalFakeAnalysisSDK:
    """No HTTP, credentials, imports of provider SDK, retries or configuration."""
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
                 fake_sdk=None, evidence_repository=EvidenceRepository):
        self.sessions = sessions
        self.corpus_loader = corpus_loader
        self.confirm_synthetic = confirm_synthetic
        self.fake_sdk = fake_sdk if fake_sdk is not None else LocalFakeAnalysisSDK()
        if type(self.fake_sdk) is not LocalFakeAnalysisSDK:
            raise ValueError('LOCAL_FAKE_SDK_REQUIRED')
        self.evidence_repository = evidence_repository

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
        report = SyntheticExecution(status='FAILED', steps=[
            PreparationStep(tool=tool, purpose=purpose, required_data=needs)
            for tool, purpose, needs in EXECUTION_PLAN])
        active = report.steps[0]
        safe_error = None

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
            nonlocal safe_error
            try:
                if not protected_call.get():
                    raise LocalExecutionStopped('EXISTING_JOB_DISPATCH_REQUIRED')
                finish({'claimed': True}, {'existing_job_dispatch': True})
                start(1, {'company_id': source_id, 'news_id': news_id})
                preparation = await AnalysisPreparationService(
                    self.sessions, corpus_loader=self.corpus_loader).prepare(source_id, news_id)
                report.preparation = preparation
                if preparation.status != 'PREPARED_LOCAL' or preparation.prepared_input is None:
                    raise LocalExecutionStopped(preparation.error_code or 'LOCAL_PREPARATION_FAILED')
                payload = copy.deepcopy(preparation.prepared_input)
                if (payload['news_from_db']['content'] != news
                        or digest(payload['company_source_assertions']) != digest(company._ai_context)):
                    raise LocalExecutionStopped('CLAIM_PREPARATION_SNAPSHOT_CHANGED')
                expected = copy.deepcopy(payload['analytical_source_assertions'])
                if [fragment.model_dump() for fragment in preparation.local_stub_result.evidence] != expected:
                    raise LocalExecutionStopped('PREPARATION_EVIDENCE_MISMATCH')
                finish(payload, {'trace_id': preparation.trace_id, 'external_transfer_allowed': False})

                async def local_rag(*, question, search_query, include_evidence):
                    if question != payload['question'] or search_query != news or include_evidence is not True:
                        raise LocalExecutionStopped('LOCAL_INPUT_MISMATCH')
                    if report.fake_calls:
                        raise LocalExecutionStopped('LOCAL_FAKE_ALREADY_CALLED')
                    start(2, {'input_sha256': digest(payload)})
                    report.fake_calls += 1
                    raw = await self.fake_sdk.complete(copy.deepcopy(payload))
                    finish(raw, {'engine': FAKE_MODEL, 'paid_calls': 0})
                    start(3, {'response_sha256': digest(raw), 'evidence_sha256': digest(expected)})
                    return {'analysis': raw, 'sources': [{key: item[key] for key in ('id', 'document', 'page', 'score')}
                                                       for item in expected],
                            'evidence': copy.deepcopy(expected), 'model_name': FAKE_MODEL}

                # Existing parsing, validation, response assembly; no duplicate persistence logic.
                bundle = await analyze_for_company_with_evidence(news, company, _local_rag=local_rag)
                if ([item.model_dump() for item in bundle.evidence] != expected
                        or bundle.analysis.company_id != source_id or bundle.analysis.news != news):
                    raise LocalExecutionStopped('LOCAL_RESULT_PROVENANCE_MISMATCH')
                bundle.analysis.validation = ValidationResult(passed=False, warnings=[
                    *bundle.analysis.validation.warnings,
                    'SYNTHETIC_FAKE_ANALYSIS_NOT_FOR_DECISIONS', 'FACTUAL_ACCURACY_NOT_ASSESSED'])
                bundle.prompt_version = 'local-orchestration-v1'
                finish(bundle.model_dump(mode='json'), {'schema_valid': True, 'exact_evidence': True,
                    'factual_accuracy': 'NOT_ASSESSED', 'human_review_required': True})
                start(4, {'validated_bundle_sha256': digest(bundle.model_dump(mode='json'))})
                return bundle
            except Exception as error:
                safe_error = error.code if isinstance(error, LocalExecutionStopped) else 'LOCAL_EXECUTION_FAILED'
                raise

        try:
            self._check_target(source_id)
            start(0, {'source_id': source_id, 'news_id': news_id})
            saved = await CompanyAnalysisService(self.sessions, analyzer=analyzer,
                evidence_repository=self.evidence_repository).analyze_saved(source_id, news_id)
            result = saved.cached_response or CreatedCompanyAnalysis(run_id=saved.run_id,
                insight_id=saved.insight_id, news_id=saved.news_id, company_id=source_id,
                analysis=saved.result.analysis)
            report.run_id = saved.run_id
            report.result = result
            report.status = 'REUSED' if saved.reused else 'COMPLETED'
            finish(result.model_dump(mode='json'), {'run_id': saved.run_id, 'insight_id': saved.insight_id,
                'reused': saved.reused, 'existing_atomic_commit': not saved.reused})
        except LocalExecutionStopped as error:
            report.status, report.error_code = 'REJECTED', error.code
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
                active.status = 'FAILED'
                active.result = {'code': report.error_code}
            for step in report.steps:
                if step.status == 'PENDING':
                    step.status = 'SKIPPED'
        return report
