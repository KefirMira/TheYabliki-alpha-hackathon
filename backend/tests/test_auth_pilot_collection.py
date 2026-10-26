"""Synthetic PostgreSQL upgrade tests; all new SDK records are FAKE_TEST_ONLY."""
import asyncio
import json
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from main import app
from sqlalchemy.engine import make_url
from evaluation.pilot_collection import fake_record
from pilot_collection_demo import _apply_records
from saved_pilot_demo import import_pilot,MARKER,LOGIN
from services.pilot_collection_input import registry
from test_news_identity_migration import isolated_database,identity_dsn,DATABASE_ROOT

pytestmark=pytest.mark.integration
PASSWORD='Synthetic-collection-viewer-test-password'


async def setup(c,name,dsn,monkeypatch,seed=True):
    for filename in ['004_news_external_identity.sql','005_saved_news_analysis_jobs.sql',
                     '006_news_company_matching.sql','007_auth_access.sql']:
        await c.execute((DATABASE_ROOT/'migrations'/filename).read_text(encoding='utf-8'))
    await c.execute("COMMENT ON DATABASE "+name+" IS '"+MARKER+"'")
    value=make_url(dsn).set(drivername='postgresql+asyncpg',database=name).render_as_string(hide_password=False)
    if seed: await import_pilot(value,name,PASSWORD,apply=True)
    monkeypatch.setenv('DATABASE_URL',value);monkeypatch.setenv('AI_MODE','demo')
    return value


async def records():
    return [await fake_record(s['scenario_id']) for s in registry()['scenarios']]


@pytest.mark.parametrize('with_user_data',[False,True])
def test_upgrade_concurrent_idempotent_preserves_legacy_user_data_and_acl(identity_dsn,monkeypatch,with_user_data):
    async def scenario():
        async with isolated_database(identity_dsn) as (c,name):
            value=await setup(c,name,identity_dsn,monkeypatch)
            legacy=await c.fetchval('SELECT to_jsonb(a)::text FROM company_news_analyses a WHERE id=1')
            legacy_evidence=await c.fetchval('SELECT jsonb_agg(to_jsonb(e) ORDER BY id)::text FROM insight_evidence e')
            if with_user_data:
                await c.execute("INSERT INTO companies(source_id,name) VALUES ('SYNTH-USER-OWNED','Unrelated synthetic profile')")
                await c.execute("INSERT INTO news_articles(title,content,input_kind) VALUES ('User owned synthetic','Private synthetic user text','MANUAL')")
            user_data=await c.fetchval("SELECT jsonb_agg(to_jsonb(c))::text FROM companies c WHERE source_id='SYNTH-USER-OWNED'")
            fake=await records()
            result=await asyncio.gather(*(_apply_records(value,name,PASSWORD,fake,fake_test=True) for _ in range(8)))
            assert sum(r['created'] for r in result)==8
            assert sum(r['unchanged'] for r in result)==56
            assert await c.fetchval('SELECT count(*) FROM company_news_analyses')==9
            assert await c.fetchval('SELECT count(*) FROM companies')==(4 if with_user_data else 3)
            assert await c.fetchval('SELECT to_jsonb(a)::text FROM company_news_analyses a WHERE id=1')==legacy
            assert await c.fetchval('SELECT jsonb_agg(to_jsonb(e) ORDER BY id)::text FROM insight_evidence e WHERE company_news_analysis_id=1')==legacy_evidence
            assert await c.fetchval("SELECT jsonb_agg(to_jsonb(c))::text FROM companies c WHERE source_id='SYNTH-USER-OWNED'")==user_data
            assert await c.fetchval('SELECT count(*) FROM news_analysis_jobs')==0
            with TestClient(app) as client:
                token=client.post('/api/auth/login',json={'login':LOGIN,'password':PASSWORD}).json()['access_token']
                auth={'Authorization':'Bearer '+token}
                me=client.get('/api/me',headers=auth);assert len(me.json()['companies'])==3
                for profile in registry()['companies']:
                    source=profile['source_id']
                    assert client.get('/api/companies/'+source,headers=auth).status_code==200
                    feed=client.get('/api/companies/'+source+'/insights',headers=auth).json()
                    assert len(feed['items'])==3
                    for item in feed['items']:
                        card=client.get('/api/companies/'+source+'/insights/'+str(item['insight_id']),headers=auth).json()
                        assert card['status']=='COMPLETED' and card['evidence']
                        if item['insight_id']!=1:
                            meta=card['validation']['saved_pilot_collection_import']
                            assert meta['mode']=='FAKE_TEST_ONLY'
                            assert card['summary'].startswith('FAKE SDK TEST ONLY:')
                            assert all(s['provenance']['publisher'] is None and s['origin_url'].startswith('https://') for s in card['sources'])
                assert client.get('/api/companies/SYNTH-USER-OWNED/insights',headers=auth).status_code==403
                assert client.get('/api/companies/SYNTH-COLLECTION-METAL/insights/1',headers=auth).status_code==403
                assert client.post('/api/news',json={'title':'No','content':'Synthetic write','source_name':'test','source_id':'denied'},headers=auth).status_code==403
                assert client.post('/api/companies/SYNTH-COLLECTION-METAL/news/1/dataset-analyses',json={'news_external_transfer_confirmed':True},headers=auth).status_code==403
                assert client.post('/api/auth/logout',headers=auth).status_code==204
                assert client.get('/api/me',headers=auth).status_code==401
            assert (await _apply_records(value,name,PASSWORD,fake,fake_test=True))['unchanged']==8
            await c.execute("UPDATE company_news_analyses SET impact_summary='Synthetic tamper' WHERE id=2")
            with pytest.raises(ValueError,match='IMPORTED_RECORD_CHANGED'):
                await _apply_records(value,name,PASSWORD,fake,fake_test=True)
    asyncio.run(scenario())


@pytest.mark.parametrize('failure',['evidence','metadata'])
def test_collection_rollback_keeps_exact_original_pilot(identity_dsn,monkeypatch,failure):
    from repositories.evidence_repository import EvidenceRepository
    from sqlalchemy.ext.asyncio import AsyncConnection
    async def scenario():
        async with isolated_database(identity_dsn) as (c,name):
            value=await setup(c,name,identity_dsn,monkeypatch);fake=await records()
            before=await c.fetchval('SELECT to_jsonb(a)::text FROM company_news_analyses a')
            original=EvidenceRepository.create;execute=AsyncConnection.execute
            async def broken_evidence(repo,insight,fragment):
                if fragment.id==2:raise RuntimeError('synthetic rollback')
                return await original(repo,insight,fragment)
            async def broken_metadata(conn,statement,*args,**kwargs):
                if 'jsonb_set(validation' in str(statement):raise RuntimeError('synthetic rollback')
                return await execute(conn,statement,*args,**kwargs)
            target='repositories.evidence_repository.EvidenceRepository.create' if failure=='evidence' else 'sqlalchemy.ext.asyncio.AsyncConnection.execute'
            with patch(target,broken_evidence if failure=='evidence' else broken_metadata),pytest.raises(RuntimeError):
                await _apply_records(value,name,PASSWORD,fake,fake_test=True)
            for table,count in [('companies',1),('news_articles',1),('analysis_runs',1),('company_news_analyses',1),('insight_evidence',2)]:
                assert await c.fetchval('SELECT count(*) FROM '+table)==count
            assert await c.fetchval('SELECT to_jsonb(a)::text FROM company_news_analyses a')==before
    asyncio.run(scenario())


@pytest.mark.parametrize('existing_legacy',[False,True])
def test_real_release_atomic_import_and_repeat(identity_dsn,monkeypatch,existing_legacy):
    from pilot_collection_demo import approved_records,import_approved_collection
    from repositories.evidence_repository import EvidenceRepository
    async def scenario():
        async with isolated_database(identity_dsn) as (c,name):
            value=await setup(c,name,identity_dsn,monkeypatch,seed=existing_legacy)
            before=await c.fetchval("SELECT coalesce(jsonb_agg(to_jsonb(a)),'[]')::text FROM company_news_analyses a")
            original=EvidenceRepository.create
            async def broken(repo,insight,fragment):
                if fragment.document.startswith('public-'):raise RuntimeError('synthetic fault')
                return await original(repo,insight,fragment)
            with patch.object(EvidenceRepository,'create',broken),pytest.raises(RuntimeError):
                await import_approved_collection(value,name,PASSWORD)
            assert await c.fetchval("SELECT coalesce(jsonb_agg(to_jsonb(a)),'[]')::text FROM company_news_analyses a")==before
            assert await c.fetchval('SELECT count(*) FROM companies')==int(existing_legacy)
            result=await import_approved_collection(value,name,PASSWORD)
            assert result['created']==8 and result['new_llm_requests']==0
            assert await c.fetchval('SELECT count(*) FROM companies')==3
            assert await c.fetchval('SELECT count(*) FROM company_news_analyses')==9
            snapshot=await c.fetchval('SELECT jsonb_agg(to_jsonb(a) ORDER BY id)::text FROM company_news_analyses a')
            assert (await import_approved_collection(value,name,PASSWORD))['unchanged']==8
            assert await c.fetchval('SELECT jsonb_agg(to_jsonb(a) ORDER BY id)::text FROM company_news_analyses a')==snapshot
            with TestClient(app) as client:
                token=client.post('/api/auth/login',json={'login':LOGIN,'password':PASSWORD}).json()['access_token']
                headers={'Authorization':'Bearer '+token}
                assert len(client.get('/api/me',headers=headers).json()['companies'])==3
                for r in approved_records():
                    source=next(s['company_id'] for s in registry()['scenarios'] if s['scenario_id']==r['scenario_id'])
                    feed=client.get('/api/companies/'+source+'/insights',headers=headers).json()['items']
                    assert len(feed)==3
                    cards=[client.get('/api/companies/'+source+'/insights/'+str(item['insight_id']),headers=headers).json() for item in feed]
                    card=next(card for card in cards if card['validation'].get('saved_pilot_collection_import',{}).get('scenario_id')==r['scenario_id'])
                    assert card['summary']==r['normalized']['summary']
                    assert card['validation']['financial_review']==r['financial_review']
                    assert card['validation']['orchestration']==r['orchestration']
                    assert card['validation']['saved_pilot_collection_import']['content_sha256']==r['content_sha256']
                assert client.post('/api/news',json={'title':'Denied','content':'Synthetic denied write','source_name':'test','source_id':'no'},headers=headers).status_code==403
                assert client.post('/api/auth/logout',headers=headers).status_code==204
    asyncio.run(scenario())


def test_real_collection_news_collision_rolls_back(identity_dsn,monkeypatch):
    from pilot_collection_demo import import_approved_collection
    async def scenario():
        async with isolated_database(identity_dsn) as (c,name):
            value=await setup(c,name,identity_dsn,monkeypatch)
            await c.execute("INSERT INTO news_articles(title,content,input_kind,source_name,source_id) VALUES ('Unrelated synthetic','User text','MANUAL','synthetic-pilot-collection','retail-demand')")
            with pytest.raises(ValueError,match='NEWS_COLLISION'):await import_approved_collection(value,name,PASSWORD)
            assert await c.fetchval('SELECT count(*) FROM company_news_analyses')==1
            assert await c.fetchval('SELECT count(*) FROM companies')==1
            assert await c.fetchval('SELECT count(*) FROM news_articles')==2
    asyncio.run(scenario())
