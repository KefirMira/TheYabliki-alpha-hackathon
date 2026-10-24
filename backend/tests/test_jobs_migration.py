"""005 only touches disposable databases inside the isolated test server."""
import asyncio
from pathlib import Path

import asyncpg
import pytest

from db.job_schema import JOB_SCHEMA_SQL, JOB_SCHEMA_SIGNATURE
from test_news_identity_migration import isolated_database, apply, identity_dsn, rows, DATABASE_ROOT

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (DATABASE_ROOT / 'migrations/005_saved_news_analysis_jobs.sql').read_text(encoding='utf-8')


async def apply_jobs(connection):
    try:
        await connection.execute(MIGRATION)
    except Exception:
        await connection.execute('ROLLBACK')
        raise


def test_005_replay_and_history(identity_dsn):
    async def scenario():
        async with isolated_database(identity_dsn) as (connection, _):
            await apply(connection)
            before = await rows(connection)
            await apply_jobs(connection)
            signature = await connection.fetchval(JOB_SCHEMA_SQL)
            assert signature == JOB_SCHEMA_SIGNATURE
            await apply_jobs(connection)
            assert await rows(connection) == before
            assert await connection.fetchval("SELECT count(*) FROM pg_tables WHERE schemaname='public'") == 15
    asyncio.run(scenario())


@pytest.mark.parametrize('mutation', [
    'ALTER TABLE news_analysis_jobs ALTER COLUMN max_attempts DROP NOT NULL',
    'ALTER TABLE news_analysis_attempts DROP CONSTRAINT news_analysis_attempts_attempt_no_check',
    'DROP INDEX idx_news_analysis_attempts_deadline',
])
def test_005_rejects_definition_drift(identity_dsn, mutation):
    async def scenario():
        async with isolated_database(identity_dsn) as (connection, _):
            await apply(connection)
            await apply_jobs(connection)
            await connection.execute(mutation)
            with pytest.raises(asyncpg.PostgresError, match='005:'):
                await apply_jobs(connection)
    asyncio.run(scenario())


@pytest.mark.parametrize('case,sqlstate', [('duplicate', '23505'), ('company', '23503'),
    ('attempt_limit', '23514'), ('payload', '23514')])
def test_005_constraints(identity_dsn, case, sqlstate):
    async def scenario():
        async with isolated_database(identity_dsn) as (c, _):
            await apply(c)
            await apply_jobs(c)
            a = await c.fetchval("INSERT INTO companies(name) VALUES ('Synthetic A') RETURNING id")
            b = await c.fetchval("INSERT INTO companies(name) VALUES ('Synthetic B') RETURNING id")
            n = await c.fetchval("INSERT INTO news_articles(title,content) VALUES ('Synthetic','Synthetic') RETURNING id")
            r = await c.fetchval("INSERT INTO analysis_runs(company_id,analysis_type,status) VALUES ($1,'NEWS','RUNNING') RETURNING id", a)
            j = await c.fetchval("INSERT INTO news_analysis_jobs(company_id,news_id) VALUES ($1,$2) RETURNING id", a, n)
            with pytest.raises(asyncpg.PostgresError) as error:
                if case == 'duplicate':
                    await c.execute("INSERT INTO news_analysis_jobs(company_id,news_id) VALUES ($1,$2)", a, n)
                else:
                    await c.execute("""INSERT INTO news_analysis_attempts
                     (job_id,attempt_no,company_id,news_id,run_id,claim_token,deadline_at,response_payload)
                     VALUES ($1,$2,$3,$4,$5,$6,now()+interval '3 minutes',$7::jsonb)""",
                     j, 3 if case == 'attempt_limit' else 1, b if case == 'company' else a,
                     n, r, __import__('uuid').uuid4(), '{}' if case == 'payload' else None)
            assert error.value.sqlstate == sqlstate
    asyncio.run(scenario())


def test_005_signature_query_matches_migration():
    assert MIGRATION.count(JOB_SCHEMA_SQL) == 2
    assert JOB_SCHEMA_SIGNATURE in MIGRATION
