import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal
import json
import sys
from types import SimpleNamespace

import pytest

from repositories.company_repository import CompanyRecord
from services import analysis_preparation_service as module
from services.company_context_service import build_context, external_transfer_guard, CompanyContextExternalTransferBlocked


def corpus():
    return [{'source': 'synthetic-policy.txt', 'page': 2, 'chunk_id': 7, 'date': '2026-01-01',
             'text': 'Синтетическая аналитика: ключевая ставка влияет на кредитование и инфляцию.'}]


def context():
    return build_context(dict(industry='Synthetic industry', revenue=Decimal('123'),
        incoming_rows=3, incoming_counterparties=2, outgoing_rows=0, outgoing_counterparties=0))


@pytest.fixture
def setup_service(monkeypatch):
    state = SimpleNamespace(connections=0, calls=[], company=True, news=True, loader_calls=0)
    record = CompanyRecord(1, 'SYNTH-PREP', 'Synthetic', 'Synthetic industry', None, Decimal('123'), None, None)
    class Session:
        @asynccontextmanager
        async def begin(self):
            yield
        async def execute(self, sql):
            state.calls.append(str(sql))
    @asynccontextmanager
    async def sessions():
        state.connections += 1
        try:
            yield Session()
        finally:
            state.connections -= 1
    class Companies:
        def __init__(self, session): pass
        async def get_by_source_id(self, source_id):
            return record if state.company else None
    class News:
        def __init__(self, session): pass
        async def get_by_id(self, news_id):
            return {'id': news_id, 'title': 'Synthetic', 'content': 'Ключевая ставка и кредитование: учебная новость.',
                    'url': 'https://synthetic.example/news', 'source_name': 'synthetic', 'source_id': 'item'} if state.news else None
    monkeypatch.setattr(module, 'CompanyRepository', Companies)
    monkeypatch.setattr(module, 'NewsRepository', News)
    async def load_context(session, company):
        assert state.connections == 1
        return context()
    def load_corpus():
        assert state.connections == 0
        assert 'services.rag_service' not in sys.modules
        state.loader_calls += 1
        return corpus()
    service = module.AnalysisPreparationService(sessions, corpus_loader=load_corpus, context_loader=load_context)
    return service, state


def test_vertical_slice_is_local_read_only_and_traceable(setup_service):
    service, state = setup_service
    report = asyncio.run(service.prepare('SYNTH-PREP', 1))
    assert report.status == 'PREPARED_LOCAL', report.error_code
    assert report.paid_calls == 0 and not report.external_transfer_allowed
    assert [step.tool for step in report.steps] == [step[0] for step in module.PLAN]
    assert all(step.input_sha256 and step.output_sha256 for step in report.steps)
    assert [step.status for step in report.steps] == ['OK']*4 + ['BLOCKED', 'OK', 'OK']
    assert state.connections == 0 and state.loader_calls == 1
    assert state.calls == ['SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY']
    payload = report.prepared_input
    assert payload['company_source_assertions']['computed']['payment_structure']['incoming']['source_rows'] == 3
    assert payload['model_assumptions'] == []
    evidence = payload['analytical_source_assertions'][0]
    assert evidence['text'] == corpus()[0]['text'] and evidence['date'] == '2026-01-01'
    assert evidence['document'] == 'synthetic-policy.txt' and evidence['page'] == 2 and evidence['chunk_id'] == 7
    assert report.local_stub_result.model_name == 'local-preparation-stub'
    assert report.local_stub_result.analysis.news == payload['news_from_db']['content']
    assert report.steps[-1].result['factual_accuracy'] == 'NOT_ASSESSED'
    with pytest.raises(CompanyContextExternalTransferBlocked):
        external_transfer_guard(payload['company_source_assertions'])


@pytest.mark.parametrize('missing,code', [('company', 'COMPANY_NOT_FOUND'), ('news', 'NEWS_NOT_FOUND')])
def test_missing_records_stop_without_tools(setup_service, missing, code):
    service, state = setup_service
    setattr(state, missing, False)
    report = asyncio.run(service.prepare('SYNTH-PREP', 1))
    assert report.status == 'FAILED' and report.error_code == code
    assert state.loader_calls == state.connections == 0
    assert all(step.status == 'SKIPPED' for step in report.steps[1:])


def test_missing_rag_is_incomplete_without_stub(setup_service):
    service, _ = setup_service
    service.corpus_loader = lambda: []
    report = asyncio.run(service.prepare('SYNTH-PREP', 1))
    assert report.status == 'INCOMPLETE' and report.error_code == 'NO_RAG_CONTEXT'
    assert report.local_stub_result is report.prepared_input is None
    assert report.steps[-1].status == 'SKIPPED'


def test_input_bound_and_failures_are_not_retried_or_logged(setup_service, monkeypatch):
    service, state = setup_service
    monkeypatch.setattr(module, 'MAX_INPUT_BYTES', 1)
    report = asyncio.run(service.prepare('SYNTH-PREP', 1))
    assert report.error_code == 'PREPARATION_INPUT_TOO_LARGE'
    assert report.local_stub_result is None and state.loader_calls == 1
    monkeypatch.setattr(module, 'MAX_INPUT_BYTES', 160000)
    def failure():
        raise RuntimeError('PRIVATE-SECRET-CONTENT')
    service.corpus_loader = failure
    report = asyncio.run(service.prepare('SYNTH-PREP', 1))
    assert report.status == 'FAILED' and 'PRIVATE-SECRET' not in report.model_dump_json()


def test_guard_cannot_be_silently_disabled(setup_service, monkeypatch):
    service, _ = setup_service
    monkeypatch.setattr(module, 'external_transfer_guard', lambda value: None)
    report = asyncio.run(service.prepare('SYNTH-PREP', 1))
    assert report.error_code == 'EXTERNAL_GUARD_DID_NOT_BLOCK' and report.local_stub_result is None


def test_repeated_and_concurrent_preparation_have_stable_inputs(setup_service):
    service, _ = setup_service
    async def scenario():
        return await asyncio.gather(*(service.prepare('SYNTH-PREP', 1) for _ in range(3)))
    reports = asyncio.run(scenario())
    assert all(report.status == 'PREPARED_LOCAL' for report in reports)
    assert len({report.steps[3].output_sha256 for report in reports}) == 1
    assert len({report.trace_id for report in reports}) == 3


def test_malformed_source_fails_closed(setup_service):
    service, _ = setup_service
    service.corpus_loader = lambda: [{**corpus()[0], 'page': 0}]
    report = asyncio.run(service.prepare('SYNTH-PREP', 1))
    assert report.status == 'FAILED' and report.local_stub_result is None


@pytest.mark.parametrize('source,news', [('', 1), ('SYNTH-PREP', 0), ('SYNTH-PREP', True)])
def test_invalid_input_does_not_read_database(setup_service, source, news):
    service, state = setup_service
    report = asyncio.run(service.prepare(source, news))
    assert report.error_code == 'INVALID_PREPARATION_INPUT' and state.calls == []
