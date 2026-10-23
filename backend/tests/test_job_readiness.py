import asyncio
import os

import httpx
import pytest
from sqlalchemy import text

from main import app
from test_job_claim_integration import job_database, identity_dsn

pytestmark=pytest.mark.integration


@pytest.mark.parametrize('mutation',[None,
    'DROP INDEX idx_news_analysis_attempts_deadline',
    'ALTER TABLE news_analysis_jobs ALTER COLUMN max_attempts DROP NOT NULL',
    'DROP TABLE news_analysis_attempts'])
def test_ready_requires_valid_005_readonly(identity_dsn,monkeypatch,mutation):
    monkeypatch.setenv('AI_MODE','demo')
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            if mutation:await c.execute(mutation)
            from contextlib import asynccontextmanager
            @asynccontextmanager
            async def readonly_sessions():
                async with sessions() as s:
                    await s.execute(text('SET TRANSACTION READ ONLY'))
                    yield s
            previous=getattr(app.state,'company_sessions',None)
            app.state.company_sessions=readonly_sessions
            try:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                    response=await client.get('/ready')
                assert response.status_code==(503 if mutation else 200)
                assert response.json()['checks']['database'] is (mutation is None)
            finally:
                app.state.company_sessions=previous
    asyncio.run(scenario())
