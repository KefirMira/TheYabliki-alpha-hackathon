"""Fixed local preparation graph: read-only SQL, existing RAG, no SDK/tool loop/jobs."""
import hashlib
import json
from uuid import uuid4

from sqlalchemy import text

from repositories.company_repository import CompanyRepository
from repositories.news_repository import NewsRepository
from schemas.analysis_preparation import AnalysisPreparation, PreparationStep
from schemas.persisted_analysis import RetrievedEvidence
from services.company_context_service import (
    load_company_context, serialize_context, external_transfer_guard,
    CompanyContextExternalTransferBlocked,
)
from services.company_profile_service import to_company_profile
from services.knowledge_base_service import load_knowledge_base
from services.personalization_service import analyze_for_company_with_evidence
from services.search_service import search_chunks
from services.preparation_diagnostics import safe_diagnostic

MAX_INPUT_BYTES = 160_000
PLAN = (
    ('load_snapshot', 'Read the selected saved news and company, without inferring a match.', ['news_id', 'company_source_id']),
    ('company_context', 'Load permitted source assertions, derived counts and unknowns.', ['company_id']),
    ('rag_search', 'Retrieve at most three local analytical fragments.', ['exact_news_content', 'local_corpus']),
    ('prepare_input', 'Separate news, DB assertions, source text and model assumptions.', ['context', 'news_metadata', 'retrieved_evidence']),
    ('transfer_check', 'Apply the existing external disclosure prohibition.', ['company_context']),
    ('local_stub', 'Exercise response preparation locally, without model inference.', ['bounded_input']),
    ('self_check', 'Validate input identity, schema and exact source provenance; require human review.', ['stub_result', 'evidence']),
)


def digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


class PreparationStopped(Exception):
    def __init__(self, code):
        self.code = code


class AnalysisPreparationService:
    """Internal read-only entry point. There is deliberately no external analyzer argument."""
    def __init__(self, sessions, *, corpus_loader=load_knowledge_base, context_loader=load_company_context):
        self.sessions = sessions
        self.corpus_loader = corpus_loader
        self.context_loader = context_loader

    async def prepare(self, source_id: str, news_id: int) -> AnalysisPreparation:
        report = AnalysisPreparation(trace_id=str(uuid4()), steps=[
            PreparationStep(tool=tool, purpose=purpose, required_data=needs)
            for tool, purpose, needs in PLAN
        ])
        active = None

        def start(tool, inputs):
            nonlocal active
            active = next(step for step in report.steps if step.tool == tool)
            active.status = 'RUNNING'
            active.input_sha256 = digest(inputs)

        def finish(value, summary, status='OK'):
            active.output_sha256 = digest(value)
            active.result = summary
            active.status = status

        try:
            start('load_snapshot', {'source_id': source_id, 'news_id': news_id})
            if not source_id.strip() or isinstance(news_id, bool) or not isinstance(news_id, int) or news_id < 1:
                raise PreparationStopped('INVALID_PREPARATION_INPUT')
            async with self.sessions() as session, session.begin():
                # One consistent source snapshot; no database connection beyond this block.
                await session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
                company_record = await CompanyRepository(session).get_by_source_id(source_id)
                if company_record is None:
                    raise PreparationStopped('COMPANY_NOT_FOUND')
                row = await NewsRepository(session).get_by_id(news_id)
                if row is None:
                    raise PreparationStopped('NEWS_NOT_FOUND')
                news = dict(row)
                content = news.get('content')
                if not isinstance(content, str) or not content.strip() or len(content) > 100_000:
                    raise PreparationStopped('NEWS_NOT_ANALYZABLE')
                finish(news, {'origin': 'news_articles + companies', 'matching': 'EXPLICIT_PAIR_NOT_VERIFIED'})
                start('company_context', {'company_id': company_record.id})
                context = await self.context_loader(session, company_record)
                if not isinstance(context, dict) or not all(key in context for key in ('facts', 'computed', 'missing', 'model_assumptions')):
                    raise PreparationStopped('INVALID_COMPANY_CONTEXT')
                serialize_context(context)
                finish(context, {'origin': 'company_context_service', 'missing': context['missing']})

            start('rag_search', {'query_sha256': digest(content), 'top_k': 3})
            selected = search_chunks(content, self.corpus_loader(), top_k=3)
            if not selected:
                raise PreparationStopped('NO_RAG_CONTEXT')
            # Chunk loader metadata is preserved; absent dates stay unknown, never inferred.
            evidence = [RetrievedEvidence(id=i, document=chunk['source'], page=chunk['page'],
                chunk_id=chunk.get('chunk_id', 1), date=chunk.get('date'),
                score=chunk['score'], text=chunk['text']).model_dump()
                for i, chunk in enumerate(selected, 1)]
            finish(evidence, {'count': len(evidence), 'fragments': [
                {key: value[key] for key in ('id', 'document', 'page', 'chunk_id', 'date')}
                for value in evidence], 'score_is_confidence': False})
            company = to_company_profile(company_record)
            company._ai_context = context

            async def local_rag(*, question, search_query, include_evidence):
                start('prepare_input', {'news_sha256': digest(news), 'context_sha256': digest(context),
                                        'evidence_sha256': digest(evidence)})
                if search_query != content or include_evidence is not True:
                    raise PreparationStopped('PREPARATION_INPUT_MISMATCH')
                payload = {'news_from_db': news, 'company_source_assertions': context,
                           'analytical_source_assertions': evidence, 'model_assumptions': [],
                           'question': question, 'mode': 'LOCAL_STUB_ONLY'}
                size = len(json.dumps(payload, ensure_ascii=False, default=str, allow_nan=False).encode('utf-8'))
                if size > MAX_INPUT_BYTES:
                    raise PreparationStopped('PREPARATION_INPUT_TOO_LARGE')
                report.prepared_input = payload
                finish(payload, {'utf8_bytes': size, 'truncated': False})
                start('transfer_check', {'company_context_sha256': digest(context)})
                try:
                    external_transfer_guard(context)
                except CompanyContextExternalTransferBlocked:
                    finish({'allowed': False}, {'code': 'COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED',
                                              'local_stub_permitted': True}, 'BLOCKED')
                else:
                    raise PreparationStopped('EXTERNAL_GUARD_DID_NOT_BLOCK')
                start('local_stub', {'input_sha256': digest(payload)})
                # Fixed built-in stub, never a caller-supplied SDK or an inferred financial conclusion.
                response = {'relevance': 'unknown', 'summary': 'Локальная проверка подготовки; анализ моделью не выполнялся.',
                            'risks': [], 'opportunities': [], 'recommendations': []}
                finish(response, {'engine': 'fixed-local-stub', 'llm_calls': 0, 'quality_assessed': False})
                start('self_check', {'response_sha256': digest(response), 'evidence_sha256': digest(evidence)})
                return {'analysis': json.dumps(response, ensure_ascii=False),
                        'sources': [{key: fragment[key] for key in ('id', 'document', 'page', 'score')}
                                    for fragment in evidence],
                        'evidence': evidence, 'model_name': 'local-preparation-stub'}

            # Reuse existing question, context rules, parsing, validation and evidence contract.
            bundle = await analyze_for_company_with_evidence(content, company, _local_rag=local_rag)
            if bundle.analysis.news != content or bundle.analysis.company_id != source_id:
                raise PreparationStopped('PREPARATION_RESULT_MISMATCH')
            if [fragment.model_dump() for fragment in bundle.evidence] != evidence:
                raise PreparationStopped('PREPARATION_EVIDENCE_MISMATCH')
            finish(bundle.model_dump(mode='json'), {'schema_valid': True, 'exact_evidence': True,
                'factual_accuracy': 'NOT_ASSESSED', 'model_self_review': 'NOT_IMPLEMENTED',
                'human_review_required': True})
            report.local_stub_result = bundle
            report.status = 'PREPARED_LOCAL'
        except Exception as error:
            report.error_code = error.code if isinstance(error, PreparationStopped) else 'PREPARATION_FAILED'
            if not isinstance(error, PreparationStopped):
                report.diagnostic = safe_diagnostic(active.tool if active is not None else 'UNKNOWN', error)
            report.status = 'INCOMPLETE' if report.error_code == 'NO_RAG_CONTEXT' else 'FAILED'
            if active is not None:
                active.status = 'FAILED'
                active.result = {'code': report.error_code}
        finally:
            for step in report.steps:
                if step.status == 'PENDING':
                    step.status = 'SKIPPED'
        return report
