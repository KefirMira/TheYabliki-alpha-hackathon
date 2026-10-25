"""Real PostgreSQL + real ACL; no paid analysis or SDK."""
import asyncio
import json
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from main import app
from saved_pilot_demo import import_pilot, approved, fingerprint, MARKER, LOGIN
from services.auth_service import HASHER
from test_news_identity_migration import isolated_database, identity_dsn, DATABASE_ROOT

pytestmark = pytest.mark.integration
PASSWORD = 'Invented-pilot-password-only-for-tests'


async def setup(c, name, dsn, monkeypatch):
    for f in ['004_news_external_identity.sql','005_saved_news_analysis_jobs.sql',
              '006_news_company_matching.sql','007_auth_access.sql']:
        await c.execute((DATABASE_ROOT/'migrations'/f).read_text(encoding='utf-8'))
    value = make_url(dsn).set(drivername='postgresql+asyncpg',database=name).render_as_string(hide_password=False)
    monkeypatch.setenv('DATABASE_URL',value)
    monkeypatch.setenv('AI_MODE','demo')
    return value


def test_import_concurrency_replay_http_acl_and_unchanged_content(identity_dsn, monkeypatch):
    async def scenario():
        async with isolated_database(identity_dsn) as (c,name):
            value = await setup(c,name,identity_dsn,monkeypatch)
            with pytest.raises(ValueError,match='MARKER'):
                await import_pilot(value,name,PASSWORD,apply=True)
            await c.execute(f"COMMENT ON DATABASE {name} IS '{MARKER}'")
            assert (await import_pilot(value,name))['state'] == 'PLAN_ONLY'
            assert await c.fetchval('SELECT count(*) FROM companies') == 0
            results = await asyncio.gather(*(import_pilot(value,name,PASSWORD,apply=True) for _ in range(8)))
            assert [r['state'] for r in results].count('CREATED') == 1
            assert [r['state'] for r in results].count('UNCHANGED') == 7
            assert await c.fetchval('SELECT count(*) FROM companies') == 1
            assert await c.fetchval('SELECT count(*) FROM auth_users') == 1
            assert await c.fetchval('SELECT count(*) FROM company_news_analyses') == 1
            assert await c.fetchval('SELECT count(*) FROM insight_evidence') == 2
            assert await c.fetchval('SELECT count(*) FROM news_analysis_jobs') == 0
            assert await c.fetchval('SELECT count(*) FROM news_analysis_attempts') == 0
            data,bundle=approved()
            company=bundle.analysis.company_id
            insight=await c.fetchval('SELECT id FROM company_news_analyses')
            stored=json.loads(await c.fetchval('SELECT validation::text FROM company_news_analyses'))
            assert stored['orchestration'] == data['orchestration']
            assert stored['financial_review'] == data['financial_review']
            before=await c.fetchval("SELECT jsonb_agg(to_jsonb(t))::text FROM company_news_analyses t")
            with TestClient(app) as client:
                assert client.get(f'/api/companies/{company}').status_code == 401
                token=client.post('/api/auth/login',json={'login':LOGIN,'password':PASSWORD}).json()['access_token']
                auth={'Authorization':'Bearer '+token}
                assert len(client.get('/api/me',headers=auth).json()['companies']) == 1
                card=client.get(f'/api/companies/{company}/insights/{insight}',headers=auth)
                assert card.status_code == 200
                body=card.json()
                for key in ['relevance','summary','risks','opportunities','recommendations']:
                    assert body[key] == bundle.analysis.model_dump()[key]
                assert [e['text'] for e in body['evidence']] == [f.text for f in bundle.evidence]
                assert all(s['synthetic'] and s['provenance']['publisher'] is None for s in body['sources'])
                assert all(e['evidence_type']=='DOCUMENT' for e in body['evidence'])
                assert client.get('/api/companies/FOREIGN/insights',headers=auth).status_code == 403
                assert client.post(f'/api/companies/{company}/news/{body["news"]["id"]}/analyses',headers=auth,json={}).status_code == 403
                assert client.post('/api/news',headers=auth,json={'title':'Synthetic attempt','content':'Invented news','source_name':'synthetic-demo','source_id':'SYNTH-FORBIDDEN'}).status_code == 403
                assert client.post('/api/auth/logout',headers=auth).status_code == 204
                assert client.get('/api/me',headers=auth).status_code == 401
            assert (await import_pilot(value,name,PASSWORD,apply=True))['state'] == 'UNCHANGED'
            assert await c.fetchval("SELECT jsonb_agg(to_jsonb(t))::text FROM company_news_analyses t") == before
            with pytest.raises(ValueError,match='CREDENTIALS'):
                await import_pilot(value,name,'Different-test-password',apply=True)
            # An independently authenticated actor cannot see the imported result.
            other=uuid4()
            await c.execute('INSERT INTO auth_users(id,login,password_hash) VALUES ($1,$2,$3)',other,'synthetic-other',HASHER.hash(PASSWORD))
            with TestClient(app) as client:
                token=client.post('/api/auth/login',json={'login':'synthetic-other','password':PASSWORD}).json()['access_token']
                auth={'Authorization':'Bearer '+token}
                assert client.get(f'/api/companies/{company}/insights/{insight}',headers=auth).status_code == 403
                assert client.get(f'/api/companies/{company}',headers=auth).status_code == 403
            with pytest.raises(ValueError,match='SNAPSHOT_CHANGED'):
                await import_pilot(value,name,PASSWORD,apply=True)
    asyncio.run(scenario())


@pytest.mark.parametrize('failure',['second_evidence','trace'])
def test_atomic_rollback(identity_dsn,monkeypatch,failure):
    from repositories.evidence_repository import EvidenceRepository
    from sqlalchemy.ext.asyncio import AsyncConnection
    async def scenario():
        async with isolated_database(identity_dsn) as (c,name):
            value=await setup(c,name,identity_dsn,monkeypatch)
            await c.execute(f"COMMENT ON DATABASE {name} IS '{MARKER}'")
            original=EvidenceRepository.create
            async def broken(repo,insight,fragment):
                if fragment.id==2:raise RuntimeError('synthetic evidence failure')
                return await original(repo,insight,fragment)
            execute=AsyncConnection.execute
            async def broken_trace(conn,statement,*args,**kwargs):
                if str(statement).startswith('UPDATE company_news_analyses SET validation'):
                    raise RuntimeError('synthetic trace failure')
                return await execute(conn,statement,*args,**kwargs)
            target='repositories.evidence_repository.EvidenceRepository.create' if failure=='second_evidence' else 'sqlalchemy.ext.asyncio.AsyncConnection.execute'
            with patch(target,broken if failure=='second_evidence' else broken_trace),pytest.raises(RuntimeError):
                await import_pilot(value,name,PASSWORD,apply=True)
            for table in ['companies','auth_users','auth_user_companies','auth_news_grants','news_articles','analysis_runs','company_news_analyses','insight_evidence']:
                assert await c.fetchval(f'SELECT count(*) FROM {table}')==0
    asyncio.run(scenario())


def test_nonempty_or_foreign_demo_refused(identity_dsn,monkeypatch):
    async def scenario():
        async with isolated_database(identity_dsn) as (c,name):
            value=await setup(c,name,identity_dsn,monkeypatch)
            await c.execute("INSERT INTO companies(source_id,name) VALUES ('SYNTH-OLD','Invented old profile')")
            await c.execute(f"COMMENT ON DATABASE {name} IS '{MARKER}'")
            with pytest.raises(ValueError,match='EMPTY'):
                await import_pilot(value,name,PASSWORD,apply=True)
            assert await c.fetchval('SELECT count(*) FROM companies')==1
    asyncio.run(scenario())
