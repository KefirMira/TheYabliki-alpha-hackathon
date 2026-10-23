import asyncio
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from repositories.news_analysis_job_repository import AnalysisConflict, NewsAnalysisJobRepository
from test_news_identity_migration import isolated_database, apply, identity_dsn
from test_jobs_migration import apply_jobs

pytestmark = pytest.mark.integration


@asynccontextmanager
async def job_database(dsn):
    async with isolated_database(dsn) as (connection, name):
        await apply(connection)
        await apply_jobs(connection)
        for source in ('SYNTH-COMPANY-A','SYNTH-COMPANY-B'):
            await connection.execute("INSERT INTO companies(source_id,name) VALUES ($1,'Synthetic')", source)
        news = await connection.fetchval("INSERT INTO news_articles(title,content) VALUES ('Synthetic','Synthetic saved news') RETURNING id")
        engine = create_async_engine(make_url(dsn).set(drivername='postgresql+asyncpg',database=name), poolclass=NullPool)
        try:
            yield engine, async_sessionmaker(engine,expire_on_commit=False), connection, news
        finally:
            await engine.dispose()


def test_atomic_claim_eight_independent_connections(identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (_, sessions, c, news):
            company = await c.fetchval("SELECT id FROM companies WHERE source_id='SYNTH-COMPANY-A'")
            barrier = asyncio.Barrier(8)
            async def reserve():
                await barrier.wait()
                async with sessions() as s:
                    try:
                        async with s.begin():
                            return await NewsAnalysisJobRepository(s).claim(company,news)
                    except AnalysisConflict as error:
                        return error
            results = await asyncio.wait_for(asyncio.gather(*(reserve() for _ in range(8))),20)
            assert sum(not isinstance(r,AnalysisConflict) for r in results)==1
            assert [r.code for r in results if isinstance(r,AnalysisConflict)]==['ANALYSIS_ALREADY_RUNNING']*7
            assert await c.fetchval('SELECT count(*) FROM analysis_runs')==1
            assert await c.fetchval('SELECT count(*) FROM news_analysis_attempts')==1
    asyncio.run(scenario())


def test_claim_rollback_and_company_independence(identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (_, sessions, c, news):
            companies=await c.fetch('SELECT id FROM companies ORDER BY id')
            async with sessions() as s:
                with pytest.raises(RuntimeError):
                    async with s.begin():
                        await NewsAnalysisJobRepository(s).claim(companies[0]['id'],news)
                        raise RuntimeError('Synthetic rollback')
            assert await c.fetchval('SELECT count(*) FROM analysis_runs')==0
            for company in companies:
                async with sessions() as s, s.begin():
                    await NewsAnalysisJobRepository(s).claim(company['id'],news)
            assert await c.fetchval('SELECT count(*) FROM analysis_runs')==2
            assert await c.fetchval('SELECT count(*) FROM news_analysis_jobs')==2
    asyncio.run(scenario())
