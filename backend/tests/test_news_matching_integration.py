import asyncio

import pytest
from sqlalchemy import text

from services.news_matching_service import NewsMatchingService
from test_job_claim_integration import job_database, identity_dsn
from test_news_identity_migration import DATABASE_ROOT

pytestmark = pytest.mark.integration
MIGRATION = DATABASE_ROOT / 'migrations/006_news_company_matching.sql'


def test_matching_persistence_concurrency_registry_update_and_history(identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (_, sessions, c, news):
            await c.execute(MIGRATION.read_text(encoding='utf-8'))
            await c.execute(MIGRATION.read_text(encoding='utf-8'))
            await c.execute("UPDATE companies SET name='RegistryCompany' || id")
            # Synthetic identifier, not a real tax registration.
            company = await c.fetchval("UPDATE companies SET inn='1234567890' WHERE source_id='SYNTH-COMPANY-A' RETURNING id")
            await c.execute("UPDATE news_articles SET content='Синтетический ИНН 1234567890' WHERE id=$1", news)
            before = dict(await c.fetchrow('SELECT * FROM news_articles WHERE id=$1', news))
            old_run = await c.fetchval("INSERT INTO analysis_runs(company_id,analysis_type,status) VALUES($1,'NEWS','COMPLETED') RETURNING id", company)
            old_analysis = await c.fetchval("""INSERT INTO company_news_analyses(analysis_run_id,company_id,news_id)
                VALUES($1,$2,$3) RETURNING id""", old_run, company, news)
            await c.execute("INSERT INTO insight_evidence(company_news_analysis_id,evidence_type,evidence_text) VALUES($1,'DOCUMENT','Synthetic old evidence')", old_analysis)
            history = await c.fetchval("SELECT md5(string_agg(row_to_json(t)::text,'' ORDER BY id)) FROM insight_evidence t")
            service = NewsMatchingService(sessions)
            barrier = asyncio.Barrier(8)
            async def run():
                await barrier.wait()
                return await service.match(news)
            results = await asyncio.wait_for(asyncio.gather(*(run() for _ in range(8))), 30)
            assert len({r['id'] for r in results}) == 1
            assert sum(not r['reused'] for r in results) == 1
            assert results[0]['status'] == 'MATCHED'
            assert results[0]['matched_company_ids'] == [company]
            assert await c.fetchval('SELECT count(*) FROM news_company_match_candidates') == 1
            await c.execute("UPDATE companies SET inn='1234567890' WHERE source_id='SYNTH-COMPANY-B'")
            ambiguous = await service.match(news)
            assert ambiguous['status'] == 'AMBIGUOUS' and ambiguous['matched_company_ids'] == []
            assert ambiguous['id'] != results[0]['id']
            assert len(ambiguous['candidates']) == 2
            assert (await service.show(news, results[0]['id']))['status'] == 'MATCHED'
            assert dict(await c.fetchrow('SELECT * FROM news_articles WHERE id=$1', news)) == before
            assert await c.fetchval('SELECT count(*) FROM analysis_runs') == 1
            assert await c.fetchval("SELECT md5(string_agg(row_to_json(t)::text,'' ORDER BY id)) FROM insight_evidence t") == history
            from db.matching_schema import MATCH_SCHEMA_SQL, MATCH_SCHEMA_SIGNATURE
            assert await c.fetchval(MATCH_SCHEMA_SQL) == MATCH_SCHEMA_SIGNATURE
    asyncio.run(scenario())


@pytest.mark.parametrize('mutation', [
    'DROP INDEX ix_news_company_match_company',
    'ALTER TABLE company_verified_names ALTER COLUMN provenance DROP NOT NULL',
    'DROP TABLE news_company_match_candidates',
])
def test_006_replay_rejects_schema_drift(identity_dsn, mutation):
    import asyncpg
    async def scenario():
        async with job_database(identity_dsn) as (_, sessions, c, news):
            await c.execute(MIGRATION.read_text(encoding='utf-8'))
            await c.execute(mutation)
            with pytest.raises(asyncpg.RaiseError, match='006: catalogue definition mismatch'):
                await c.execute(MIGRATION.read_text(encoding='utf-8'))
            await c.execute('ROLLBACK')
    asyncio.run(scenario())


def test_006_constraints_and_selected_sql(identity_dsn):
    import asyncpg
    from db.matching_schema import MATCH_SCHEMA_SQL, MATCH_SCHEMA_SIGNATURE
    source = MIGRATION.read_text(encoding='utf-8')
    assert source.count(MATCH_SCHEMA_SQL.strip()) == 2
    assert source.count(MATCH_SCHEMA_SIGNATURE) == 2
    async def scenario():
        async with job_database(identity_dsn) as (_, sessions, c, news):
            await c.execute(source)
            for statement, error in [
                ("INSERT INTO company_verified_names(company_id,name,verified_by,provenance) VALUES(-1,'Synthetic','Reviewer','Registry')", asyncpg.ForeignKeyViolationError),
                ("INSERT INTO company_verified_names(company_id,name,verified_by,provenance) SELECT min(id),'Synthetic','','Registry' FROM companies", asyncpg.CheckViolationError),
                ("INSERT INTO news_company_match_runs(news_id,algorithm_version,news_hash,dictionary_hash,status,news_snapshot) VALUES(1,'v1','bad','bad','UNKNOWN','{}')", asyncpg.CheckViolationError),
            ]:
                with pytest.raises(error):
                    await c.execute(statement)
            assert await c.fetchval('SELECT count(*) FROM news_company_match_runs') == 0
    asyncio.run(scenario())


@pytest.mark.parametrize('mutation', [None, 'before_006',
    'DROP INDEX ix_news_company_match_latest',
    'ALTER TABLE company_verified_names ALTER COLUMN verified_by DROP NOT NULL'])
def test_ready_requires_006_readonly(identity_dsn, monkeypatch, mutation):
    import httpx
    from contextlib import asynccontextmanager
    from main import app
    monkeypatch.setenv('AI_MODE', 'demo')
    async def scenario():
        async with job_database(identity_dsn) as (_, sessions, c, news):
            if mutation != 'before_006':
                await c.execute(MIGRATION.read_text(encoding='utf-8'))
            if mutation and mutation != 'before_006':
                await c.execute(mutation)
            @asynccontextmanager
            async def readonly():
                async with sessions() as session:
                    await session.execute(text('SET TRANSACTION READ ONLY'))
                    yield session
            previous = getattr(app.state, 'company_sessions', None)
            app.state.company_sessions = readonly
            try:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    response = await client.get('/ready')
                    assert response.status_code == (200 if mutation is None else 503)
            finally:
                app.state.company_sessions = previous
    asyncio.run(scenario())


def test_matching_alias_no_match_missing_news_and_rollback(identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (_, sessions, c, news):
            await c.execute(MIGRATION.read_text(encoding='utf-8'))
            await c.execute("UPDATE companies SET name='RegistryCompany' || id")
            service = NewsMatchingService(sessions)
            await c.execute('''UPDATE companies SET source_data='{"aliases":["Synthetic saved news"]}'::jsonb''')
            assert (await service.match(news))['status'] == 'NO_MATCH'
            company = await c.fetchval("SELECT min(id) FROM companies")
            await c.execute("""INSERT INTO company_verified_names(company_id,name,verified_by,provenance)
                VALUES($1,'Synthetic saved news','synthetic reviewer','synthetic registry')""", company)
            result = await service.match(news)
            assert result['status'] == 'MATCHED'
            assert result['candidates'][0]['evidence'][0]['names'][0]['provenance'] == 'synthetic registry'
            with pytest.raises(LookupError, match='NEWS_NOT_FOUND'):
                await service.match(999999)
            assert await c.fetchval('SELECT count(*) FROM news_company_match_runs') == 2
            # A later write failure must roll back the run as well as its candidates.
            from unittest.mock import patch
            from repositories.news_match_repository import NewsMatchRepository
            original = NewsMatchRepository.save
            async def fail(self, *args, **kwargs):
                await original(self, *args, **kwargs)
                raise RuntimeError('Synthetic write failure')
            await c.execute("UPDATE companies SET name='Changed synthetic name' WHERE id=$1", company)
            with patch.object(NewsMatchRepository, 'save', fail), pytest.raises(RuntimeError):
                await service.match(news)
            assert await c.fetchval('SELECT count(*) FROM news_company_match_runs') == 2
    asyncio.run(scenario())
