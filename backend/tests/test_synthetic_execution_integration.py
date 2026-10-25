import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event

from repositories.evidence_repository import EvidenceRepository
from services import synthetic_news_execution_service as module
from services.company_analysis_service import CompanyAnalysisService
from services.company_context_service import CompanyContextExternalTransferBlocked
from synthetic_actor_fixture import job_database
from test_news_identity_migration import identity_dsn

pytestmark = pytest.mark.integration


def corpus():
    return [dict(source='synthetic-rate.pdf', page=1, chunk_id=1,
                 text='Учебная ключевая ставка и кредитование: аналитический контекст для теста.'),
            dict(source='synthetic-inflation.pdf', page=2, chunk_id=3,
                 text='Учебная ключевая ставка и инфляция: дополнительный контекст для теста.')]


async def seed(connection, news_id):
    await connection.execute("UPDATE news_articles SET content='Учебная ключевая ставка и кредитование' WHERE id=$1", news_id)
    await connection.execute("UPDATE companies SET industry='Synthetic fuel' WHERE source_id='SYNTH-COMPANY-A'")
    await connection.execute("UPDATE companies SET industry='Synthetic software' WHERE source_id='SYNTH-COMPANY-B'")


def service(sessions, **kwargs):
    return module.SyntheticNewsExecutionService(sessions, corpus_loader=corpus, confirm_synthetic=True,
        session_token=sessions.synthetic_test_token, **kwargs)


def test_synthetic_success_atomic_completion_and_cached_result(identity_dsn, monkeypatch):
    async def scenario():
        async with job_database(identity_dsn) as (engine, sessions, connection, news):
            await seed(connection, news)
            active = 0
            def checkout(*args):
                nonlocal active
                active += 1
            def checkin(*args):
                nonlocal active
                active -= 1
            event.listen(engine.sync_engine, 'checkout', checkout)
            event.listen(engine.sync_engine, 'checkin', checkin)
            sdk = module.LocalFakeAnalysisSDK()
            original = sdk.complete
            async def complete(payload):
                assert active == 0
                assert payload['company_source_assertions']['facts']['industry']['value'] == 'Synthetic fuel'
                return await original(payload)
            sdk.complete = AsyncMock(side_effect=complete)
            executor = service(sessions, fake_sdk=sdk)
            report = await executor.analyze_saved('SYNTH-COMPANY-A', news)
            assert report.status == 'COMPLETED', report.error_code
            assert report.fake_calls == 1 and report.paid_calls == 0
            sdk.complete.assert_awaited_once()
            assert all(step.status == 'OK' for step in report.steps)
            assert report.preparation.steps[4].status == 'BLOCKED'
            assert report.result.analysis.validation.passed is False
            assert 'FACTUAL_ACCURACY_NOT_ASSESSED' in report.result.analysis.validation.warnings
            assert await connection.fetchval('SELECT count(*) FROM news_articles') == 1
            assert await connection.fetchval('SELECT count(*) FROM company_news_analyses') == 1
            stored = await connection.fetch('SELECT * FROM insight_evidence ORDER BY id')
            expected = report.preparation.prepared_input['analytical_source_assertions']
            assert len(stored) == len(expected) == 2
            assert [(r['document_name'], r['document_page'], r['chunk_id'], r['evidence_text']) for r in stored] == [
                (r['document'], r['page'], r['chunk_id'], r['text']) for r in expected]
            run = await connection.fetchrow('SELECT * FROM analysis_runs')
            assert run['status'] == 'COMPLETED' and run['model_name'] == module.FAKE_MODEL
            attempt = await connection.fetchrow('SELECT * FROM news_analysis_attempts')
            assert attempt['insight_id'] == report.result.insight_id and attempt['response_payload'] is not None
            assert json.loads(attempt['response_payload']) == report.result.model_dump(mode='json')
            async def forbidden(*args, **kwargs):
                pytest.fail('COMPLETED must not prepare or generate again')
            monkeypatch.setattr(module.AnalysisPreparationService, 'prepare', forbidden)
            sdk.complete.side_effect = forbidden
            cached = await executor.analyze_saved('SYNTH-COMPANY-A', news)
            assert cached.status == 'REUSED' and cached.fake_calls == 0 and cached.preparation is None
            assert cached.result == report.result
            assert all(step.status == 'SKIPPED' for step in cached.steps[1:])
            sdk.complete.assert_awaited_once()
            assert await connection.fetchval('SELECT count(*) FROM analysis_runs') == 1
            assert active == 0
    asyncio.run(scenario())


def test_eight_concurrent_synthetic_runs_have_one_dispatch(identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (_, sessions, connection, news):
            await seed(connection, news)
            entered, release = asyncio.Event(), asyncio.Event()
            sdk = module.LocalFakeAnalysisSDK()
            original = sdk.complete
            async def wait(payload):
                entered.set()
                await release.wait()
                return await original(payload)
            sdk.complete = AsyncMock(side_effect=wait)
            executor = service(sessions, fake_sdk=sdk)
            barrier = asyncio.Barrier(8)
            async def execute():
                await barrier.wait()
                return await executor.analyze_saved('SYNTH-COMPANY-A', news)
            tasks = [asyncio.create_task(execute()) for _ in range(8)]
            try:
                await asyncio.wait_for(entered.wait(), 10)
                done, pending = await asyncio.wait(tasks, timeout=3)
                assert len(done) == 7 and len(pending) == 1
                assert all(task.result().error_code == 'ANALYSIS_ALREADY_RUNNING' for task in done)
            finally:
                release.set()
                results = await asyncio.wait_for(asyncio.gather(*tasks), 15)
            assert [r.status for r in results].count('COMPLETED') == 1
            assert sum(r.fake_calls for r in results) == 1
            sdk.complete.assert_awaited_once()
            for table in ['analysis_runs', 'news_analysis_jobs', 'news_analysis_attempts', 'company_news_analyses']:
                assert await connection.fetchval('SELECT count(*) FROM '+table) == 1
            stored = json.loads(await connection.fetchval('SELECT validation::text FROM company_news_analyses'))
            assert stored['orchestration']['drafts'] == 1
            assert stored['orchestration']['status'] == 'COMPLETED'
            assert stored['orchestration']['decisions'] <= 3
    asyncio.run(scenario())


@pytest.mark.parametrize('failure', ['fake_error', 'invalid_json', 'invalid_evidence', 'evidence_write'])
def test_synthetic_failure_uses_existing_failed_review_without_partial_results(identity_dsn, monkeypatch, failure):
    async def scenario():
        async with job_database(identity_dsn) as (_, sessions, connection, news):
            await seed(connection, news)
            sdk = module.LocalFakeAnalysisSDK()
            original = sdk.complete
            sdk.complete = AsyncMock(side_effect=original)
            if failure == 'fake_error': sdk.complete.side_effect = RuntimeError('PRIVATE-FAKE-ERROR')
            if failure == 'invalid_json': sdk.complete.side_effect = None; sdk.complete.return_value = '{'
            if failure == 'invalid_evidence':
                analyze = module.analyze_for_company_with_evidence
                async def tamper(*args, **kwargs):
                    bundle = await analyze(*args, **kwargs)
                    bundle.evidence[0].text = 'FABRICATED FRAGMENT'
                    return bundle
                monkeypatch.setattr(module, 'analyze_for_company_with_evidence', tamper)
            class FailEvidence(EvidenceRepository):
                written = 0
                async def create(self, insight, fragment):
                    type(self).written += 1
                    if self.written == 2: raise RuntimeError('PRIVATE-WRITE-ERROR')
                    return await super().create(insight, fragment)
            executor = service(sessions, fake_sdk=sdk,
                evidence_repository=FailEvidence if failure == 'evidence_write' else EvidenceRepository)
            report = await executor.analyze_saved('SYNTH-COMPANY-A', news)
            assert report.status == 'FAILED' and report.result is None
            assert report.run_id is not None and report.fake_calls == 1
            assert 'PRIVATE-' not in report.model_dump_json()
            if failure == 'invalid_evidence': assert report.error_code == 'LOCAL_RESULT_PROVENANCE_MISMATCH'
            if failure == 'evidence_write': assert FailEvidence.written == 2
            assert await connection.fetchval('SELECT status FROM analysis_runs') == 'FAILED'
            attempt = await connection.fetchrow('SELECT * FROM news_analysis_attempts')
            assert attempt['retry_policy'] == 'REVIEW_REQUIRED'
            assert attempt['insight_id'] is attempt['response_payload'] is None
            assert await connection.fetchval('SELECT count(*) FROM company_news_analyses') == 0
            assert await connection.fetchval('SELECT count(*) FROM insight_evidence') == 0
            assert await connection.fetchval('SELECT count(*) FROM news_articles') == 1
            repeated = await executor.analyze_saved('SYNTH-COMPANY-A', news)
            assert repeated.status == 'CONFLICT' and repeated.error_code == 'ANALYSIS_RETRY_REQUIRED'
            assert repeated.fake_calls == 0
            sdk.complete.assert_awaited_once()
    asyncio.run(scenario())


def test_changed_context_after_claim_stops_before_fake_call(identity_dsn, monkeypatch):
    async def scenario():
        async with job_database(identity_dsn) as (_, sessions, connection, news):
            await seed(connection, news)
            prepare = module.AnalysisPreparationService.prepare
            async def change_then_prepare(preparer, *args, **kwargs):
                await connection.execute("UPDATE companies SET industry='Synthetic changed profile' WHERE source_id='SYNTH-COMPANY-A'")
                return await prepare(preparer, *args, **kwargs)
            monkeypatch.setattr(module.AnalysisPreparationService, 'prepare', change_then_prepare)
            sdk = module.LocalFakeAnalysisSDK()
            sdk.complete = AsyncMock(side_effect=AssertionError('Must not generate on changed input'))
            report = await service(sessions, fake_sdk=sdk).analyze_saved('SYNTH-COMPANY-A', news)
            assert report.status == 'FAILED' and report.error_code == 'CLAIM_PREPARATION_SNAPSHOT_CHANGED'
            assert report.fake_calls == 0
            sdk.complete.assert_not_awaited()
            assert await connection.fetchval('SELECT status FROM analysis_runs') == 'FAILED'
            assert await connection.fetchval('SELECT count(*) FROM company_news_analyses') == 0
    asyncio.run(scenario())


def test_company_independence_missing_input_and_external_guard(identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (_, sessions, connection, news):
            await seed(connection, news)
            executor = service(sessions)
            a, b = await asyncio.gather(executor.analyze_saved('SYNTH-COMPANY-A', news),
                                       executor.analyze_saved('SYNTH-COMPANY-B', news))
            assert a.status == b.status == 'COMPLETED'
            assert a.result.insight_id != b.result.insight_id
            assert a.preparation.prepared_input['company_source_assertions'] != b.preparation.prepared_input['company_source_assertions']
            for source, target, code in [('SYNTH-MISSING', news, 'ACCESS_DENIED'),
                                         ('SYNTH-COMPANY-A', news+999, 'ACCESS_DENIED')]:
                report = await executor.analyze_saved(source, target)
                assert report.status == 'REJECTED' and report.error_code == code and report.fake_calls == 0
            assert await connection.fetchval('SELECT count(*) FROM analysis_runs') == 2
            other = await connection.fetchval("INSERT INTO news_articles(title,content) VALUES ('Synthetic','Synthetic new input') RETURNING id")
            with pytest.raises(CompanyContextExternalTransferBlocked):
                await CompanyAnalysisService(sessions).analyze_saved('SYNTH-COMPANY-A', other)
            assert await connection.fetchval('SELECT count(*) FROM analysis_runs') == 2
    asyncio.run(scenario())
