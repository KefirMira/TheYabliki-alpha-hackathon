import asyncio

import pytest
from sqlalchemy import event
from sqlalchemy import text

from services.analysis_preparation_service import AnalysisPreparationService
from services.company_analysis_service import CompanyAnalysisService
from test_job_claim_integration import job_database
from test_news_identity_migration import identity_dsn

pytestmark = pytest.mark.integration


def test_preparation_real_repository_snapshot_no_writes_or_connection_during_rag(identity_dsn, bundle_factory):
    async def scenario():
        async with job_database(identity_dsn) as (engine, sessions, connection, news_id):
            await connection.execute("UPDATE companies SET industry='Synthetic fuel' WHERE source_id='SYNTH-COMPANY-A'")
            await connection.execute("UPDATE news_articles SET content='Учебная ключевая ставка и кредитование' WHERE id=$1", news_id)
            async def fake(*, company, news):
                return bundle_factory(news, company.company_id)
            saved = await CompanyAnalysisService(sessions, fake).analyze_saved('SYNTH-COMPANY-A', news_id)
            tables = ['companies', 'news_articles', 'analysis_runs', 'news_analysis_jobs',
                      'news_analysis_attempts', 'company_news_analyses', 'insight_evidence']
            async def fingerprint():
                return [await connection.fetchval('SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),\'[]\')::text FROM '+table+' t') for table in tables]
            before = await fingerprint()
            open_connections = 0
            task_connections = {}
            def checkout(dbapi, record, proxy):
                nonlocal open_connections
                open_connections += 1
                owner = asyncio.current_task()
                record.info['preparation_test_owner'] = owner
                task_connections[owner] = task_connections.get(owner, 0) + 1
            def checkin(dbapi, record):
                nonlocal open_connections
                open_connections -= 1
                owner = record.info.pop('preparation_test_owner')
                task_connections[owner] -= 1
            event.listen(engine.sync_engine, 'checkout', checkout)
            event.listen(engine.sync_engine, 'checkin', checkin)
            def corpus():
                # Other preparations may still read; this task must release its own connection.
                assert task_connections.get(asyncio.current_task(), 0) == 0
                return [{'source': 'synthetic.txt', 'page': 1, 'chunk_id': 2,
                         'text': 'Учебная аналитика: ключевая ставка и кредитование влияют на бизнес.'}]
            service = AnalysisPreparationService(sessions, corpus_loader=corpus)
            reports = await asyncio.gather(*(service.prepare('SYNTH-COMPANY-A', news_id) for _ in range(3)))
            assert all(report.status == 'PREPARED_LOCAL' for report in reports), [r.error_code for r in reports]
            assert len({r.steps[3].output_sha256 for r in reports}) == 1
            assert reports[0].prepared_input['analytical_source_assertions'][0]['date'] is None
            second = await service.prepare('SYNTH-COMPANY-B', news_id)
            assert second.status == 'PREPARED_LOCAL'
            assert second.prepared_input['company_source_assertions'] != reports[0].prepared_input['company_source_assertions']
            for source, news, code in [('MISSING', news_id, 'COMPANY_NOT_FOUND'),
                                       ('SYNTH-COMPANY-A', news_id+999, 'NEWS_NOT_FOUND')]:
                assert (await service.prepare(source, news)).error_code == code
            assert open_connections == 0 and before == await fingerprint()
            async def forbidden_write(session, record):
                await session.execute(text("UPDATE companies SET industry='MUST_NOT_COMMIT'"))
            blocked = await AnalysisPreparationService(sessions, corpus_loader=corpus,
                context_loader=forbidden_write).prepare('SYNTH-COMPANY-A', news_id)
            assert blocked.status == 'FAILED' and blocked.error_code == 'PREPARATION_FAILED'
            assert blocked.diagnostic.stage == 'company_context'
            assert blocked.diagnostic.family == 'DATABASE' and blocked.diagnostic.retry_allowed is False
            assert before == await fingerprint()
            reused = await CompanyAnalysisService(sessions).analyze_saved('SYNTH-COMPANY-A', news_id)
            assert reused.reused and reused.insight_id == saved.insight_id
    asyncio.run(scenario())
