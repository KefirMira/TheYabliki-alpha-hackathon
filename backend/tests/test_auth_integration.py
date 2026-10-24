"""Real independent PostgreSQL transactions; no auth overrides and no external SDK."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from main import app
from api.company_analyses import get_analysis_analyzer
from services import auth_service
from test_news_identity_migration import isolated_database, identity_dsn, DATABASE_ROOT

pytestmark=pytest.mark.integration
MIGRATION=(DATABASE_ROOT/'migrations/007_auth_access.sql').read_text(encoding='utf-8')
PASSWORD='Entirely-synthetic-password'


@asynccontextmanager
async def auth_database(dsn,monkeypatch):
    async with isolated_database(dsn) as (c,name):
        for filename in ['004_news_external_identity.sql','005_saved_news_analysis_jobs.sql',
                         '006_news_company_matching.sql','007_auth_access.sql']:
            await c.execute((DATABASE_ROOT/'migrations'/filename).read_text(encoding='utf-8'))
        ids={}
        for login in ['alice','bob','charlie']:
            ids[login]=uuid4()
            await c.execute('INSERT INTO auth_users(id,login,password_hash) VALUES ($1,$2,$3)',
                            ids[login],login,auth_service.HASHER.hash(PASSWORD))
        for source in ['SYNTH-A','SYNTH-B']:
            await c.execute("INSERT INTO companies(source_id,name) VALUES ($1,'Synthetic only')",source)
        for login,source in [('alice','SYNTH-A'),('bob','SYNTH-A'),('charlie','SYNTH-B')]:
            await c.execute('''INSERT INTO auth_user_companies(user_id,company_id,can_analyze)
                SELECT $1,id,true FROM companies WHERE source_id=$2''',ids[login],source)
        url=make_url(dsn).set(drivername='postgresql+asyncpg',database=name)
        monkeypatch.setenv('DATABASE_URL',url.render_as_string(hide_password=False))
        monkeypatch.setenv('AI_MODE','full')
        monkeypatch.setattr(auth_service,'LOGIN_LIMITER',auth_service.LoginLimiter())
        yield c,ids


def headers(client,login):
    response=client.post('/api/auth/login',json={'login':login,'password':PASSWORD})
    assert response.status_code==200,response.text
    assert response.headers['cache-control']=='no-store'
    return {'Authorization':'Bearer '+response.json()['access_token']}


def test_full_auth_and_private_news_chain(identity_dsn,monkeypatch,bundle_factory):
    async def scenario():
        async with auth_database(identity_dsn,monkeypatch) as (c,ids):
            calls=[]
            async def fake(**kwargs):
                calls.append(kwargs['company'].company_id)
                # No request-long auth connection/transaction during model execution.
                assert app.state.company_sessions.kw['bind'].sync_engine.pool.checkedout()==0
                return bundle_factory(news=kwargs['news'],company_id=kwargs['company'].company_id)
            app.dependency_overrides[get_analysis_analyzer]=lambda:fake
            try:
                with TestClient(app) as client:
                    a,b,ch=[headers(client,name) for name in ['alice','bob','charlie']]
                    assert client.get('/api/me',headers=a).json()['companies'][0]['source_id']=='SYNTH-A'
                    assert client.get('/api/companies/SYNTH-A',headers=a).status_code==200
                    assert client.get('/api/companies/SYNTH-B',headers=a).status_code==403
                    assert client.get('/api/companies/DOES-NOT-EXIST',headers=a).status_code==403
                    news={'title':'Invented rate news','content':'Entirely synthetic news','source_name':'synthetic-test',
                          'source_id':'private-item','url':'https://example.invalid/private'}
                    saved=client.post('/api/news',headers=a,json=news)
                    assert saved.status_code==201,saved.text
                    news_id=saved.json()['news_id']
                    assert client.post('/api/news',headers=a,json=news).status_code==200
                    denied=client.post('/api/news',headers=b,json=news)
                    assert denied.status_code==403 and 'news_id' not in denied.text and 'Invented' not in denied.text
                    path=f'/api/companies/SYNTH-A/news/{news_id}/analyses'
                    assert client.post(path,headers=b).status_code==403
                    assert client.post(path.replace('SYNTH-A','SYNTH-B'),headers=a).status_code==403
                    result=client.post(path,headers=a)
                    assert result.status_code==201,result.text
                    insight=result.json()['insight_id']
                    assert client.post(path,headers=a).status_code==200 and len(calls)==1
                    assert client.post(path,headers=b).status_code==403 and len(calls)==1
                    assert len(client.get('/api/companies/SYNTH-A/insights',headers=a).json()['items'])==1
                    assert client.get('/api/companies/SYNTH-A/insights',headers=b).json()['items']==[]
                    card=f'/api/companies/SYNTH-A/insights/{insight}'
                    assert client.get(card,headers=a).status_code==200
                    assert client.get(card,headers=b).status_code==403
                    assert client.get(card,headers=ch).status_code==403
                    for legacy in ['/api/analyze','/api/analyze-rag','/api/analyze-company']:
                        assert client.post(legacy,headers=a,json={'news':'synthetic','company':{'company_id':'SYNTH-B'}}).status_code==403
                    assert len(calls)==1
                    assert client.post('/api/auth/logout',headers=a).status_code==204
                    assert client.get('/api/me',headers=a).status_code==401
                    assert client.get('/api/me',headers=b).status_code==200
                sessions=await c.fetch('SELECT token_hash FROM auth_sessions')
                assert all(len(row['token_hash'])==64 and a['Authorization'].split()[1] not in row['token_hash'] for row in sessions)
                assert await c.fetchval('SELECT count(*) FROM auth_news_grants')==1
                assert await c.fetchval('SELECT count(*) FROM analysis_runs')==1
            finally:
                app.dependency_overrides.pop(get_analysis_analyzer,None)
    asyncio.run(scenario())


def test_invalid_credentials_throttle_and_redaction(identity_dsn,monkeypatch):
    async def scenario():
        async with auth_database(identity_dsn,monkeypatch) as (c,_):
            with TestClient(app) as client:
                missing=client.post('/api/auth/login',json={'login':'unknown','password':'wrong'})
                wrong=client.post('/api/auth/login',json={'login':'alice','password':'wrong'})
                assert missing.status_code==wrong.status_code==401 and missing.json()==wrong.json()
                assert 'wrong' not in wrong.text and 'argon2' not in wrong.text
                for _ in range(4):assert client.post('/api/auth/login',json={'login':'alice','password':'wrong'}).status_code==401
                assert client.post('/api/auth/login',json={'login':'alice','password':PASSWORD}).status_code==429
            assert await c.fetchval('SELECT count(*) FROM auth_sessions')==0
    asyncio.run(scenario())


@pytest.mark.parametrize('change',['expired','revoked','disabled','membership','write_permission'])
def test_session_and_permissions_checked_on_every_request(identity_dsn,monkeypatch,change):
    async def scenario():
        async with auth_database(identity_dsn,monkeypatch) as (c,ids):
            with TestClient(app) as client:
                a=headers(client,'alice')
                assert client.get('/api/companies/SYNTH-A',headers=a).status_code==200
                if change=='expired':await c.execute("UPDATE auth_sessions SET created_at=now()-interval '2 hours',expires_at=now()-interval '1 hour'")
                if change=='revoked':await c.execute('UPDATE auth_sessions SET revoked_at=clock_timestamp()')
                if change=='disabled':await c.execute('UPDATE auth_users SET is_active=false WHERE id=$1',ids['alice'])
                if change=='membership':await c.execute('DELETE FROM auth_user_companies WHERE user_id=$1',ids['alice'])
                if change=='write_permission':await c.execute('UPDATE auth_user_companies SET can_analyze=false WHERE user_id=$1',ids['alice'])
                path='/api/companies/SYNTH-A'
                if change=='write_permission':
                    assert client.get(path,headers=a).status_code==200
                    response=client.post(path+'/analyses',headers=a,json={'news':{'text':'Synthetic'}})
                else:response=client.get(path,headers=a)
                assert response.status_code==(403 if change in ['membership','write_permission'] else 401)
            assert await c.fetchval('SELECT count(*) FROM analysis_runs')==0
    asyncio.run(scenario())


def test_acl_transaction_rollback_and_external_guard(identity_dsn,monkeypatch):
    async def scenario():
        async with auth_database(identity_dsn,monkeypatch) as (c,_):
            from repositories.auth_repository import AuthRepository
            with TestClient(app) as client:
                a=headers(client,'alice')
                response=client.post('/api/companies/SYNTH-A/analyses',headers=a,json={'news':{'text':'Synthetic'}})
                assert response.status_code==503 and response.json()['detail']['code']=='COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED'
                original=AuthRepository.grant_news
                async def fail(*args):raise RuntimeError('Synthetic grant failure')
                monkeypatch.setattr(AuthRepository,'grant_news',fail)
                with TestClient(app,raise_server_exceptions=False) as other:
                    assert other.post('/api/news',headers=a,json={'title':'Invented','content':'Synthetic'}).status_code==500
                monkeypatch.setattr(AuthRepository,'grant_news',original)
            assert await c.fetchval('SELECT count(*) FROM news_articles')==0
            assert await c.fetchval('SELECT count(*) FROM auth_news_grants')==0
            assert await c.fetchval('SELECT count(*) FROM analysis_runs')==0
    asyncio.run(scenario())


def test_migration_replay_constraints_and_no_implicit_legacy_grants(identity_dsn,monkeypatch):
    async def scenario():
        async with auth_database(identity_dsn,monkeypatch) as (c,ids):
            news=await c.fetchval("INSERT INTO news_articles(title,content) VALUES ('Old synthetic','Private old') RETURNING id")
            before=await c.fetchval('SELECT jsonb_agg(to_jsonb(n))::text FROM news_articles n')
            await c.execute(MIGRATION);await c.execute(MIGRATION)
            assert await c.fetchval('SELECT jsonb_agg(to_jsonb(n))::text FROM news_articles n')==before
            assert await c.fetchval('SELECT count(*) FROM auth_news_grants')==0
            import asyncpg
            with pytest.raises(asyncpg.CheckViolationError):
                await c.execute("UPDATE auth_users SET password_hash='plaintext' WHERE id=$1",ids['alice'])
            with pytest.raises(asyncpg.ForeignKeyViolationError):
                await c.execute('INSERT INTO auth_news_grants VALUES ($1,$2,now())',uuid4(),news)
            with TestClient(app) as client:
                a=headers(client,'alice')
                assert client.post(f'/api/companies/SYNTH-A/news/{news}/analyses',headers=a).status_code==403
    asyncio.run(scenario())


def test_eight_authorized_posts_use_existing_single_claim(identity_dsn,monkeypatch,bundle_factory):
    from concurrent.futures import ThreadPoolExecutor
    async def scenario():
        async with auth_database(identity_dsn,monkeypatch) as (c,_):
            calls=[]
            async def fake(**kwargs):
                calls.append(1)
                await asyncio.sleep(0.15)
                return bundle_factory(news=kwargs['news'],company_id=kwargs['company'].company_id)
            app.dependency_overrides[get_analysis_analyzer]=lambda:fake
            try:
                with TestClient(app) as client:
                    a=headers(client,'alice')
                    news=client.post('/api/news',headers=a,json={'title':'Concurrent synthetic','content':'Invented concurrent content'}).json()['news_id']
                    path=f'/api/companies/SYNTH-A/news/{news}/analyses'
                    with ThreadPoolExecutor(max_workers=8) as pool:
                        responses=list(pool.map(lambda _:client.post(path,headers=a),range(8)))
                    assert all(r.status_code in {200,201,409} for r in responses),[(r.status_code,r.text) for r in responses]
                    assert sum(r.status_code==201 for r in responses)==1
                    assert len(calls)==1
                assert await c.fetchval('SELECT count(*) FROM news_analysis_attempts')==1
                assert await c.fetchval('SELECT count(*) FROM company_news_analyses')==1
            finally:app.dependency_overrides.pop(get_analysis_analyzer,None)
    asyncio.run(scenario())


def test_isolated_provisioning_no_reset_and_no_real_company_mapping(identity_dsn,monkeypatch):
    from auth_demo import provision, MARKER
    from sqlalchemy.exc import IntegrityError
    async def scenario():
        async with auth_database(identity_dsn,monkeypatch) as (c,_):
            name=await c.fetchval('SELECT current_database()')
            value=make_url(identity_dsn).set(drivername='postgresql+asyncpg',database=name).render_as_string(hide_password=False)
            with pytest.raises(ValueError):await provision(value,name,'synthetic-demo',PASSWORD,'SYNTH-AUTH-A')
            assert await c.fetchval("SELECT count(*) FROM companies WHERE source_id='SYNTH-AUTH-A'")==0
            await c.execute(f"COMMENT ON DATABASE {name} IS '{MARKER}'")  # UUID name created by this test only.
            await provision(value,name,'synthetic-demo',PASSWORD,'SYNTH-AUTH-A')
            encoded=await c.fetchval("SELECT password_hash FROM auth_users WHERE login='synthetic-demo'")
            assert PASSWORD not in encoded and auth_service.verify_password(encoded,PASSWORD)
            with pytest.raises(IntegrityError):await provision(value,name,'synthetic-demo','Another-synthetic-password','SYNTH-AUTH-B')
            assert await c.fetchval("SELECT count(*) FROM companies WHERE source_id='SYNTH-AUTH-B'")==0
            assert await c.fetchval("SELECT password_hash FROM auth_users WHERE login='synthetic-demo'")==encoded
            with pytest.raises(ValueError):await provision(value,name,'synthetic-other',PASSWORD,'SYNTH-A')
    asyncio.run(scenario())


def test_readiness_requires_auth_tables_without_schema_writes(identity_dsn,monkeypatch):
    from contextlib import asynccontextmanager
    from sqlalchemy import text
    async def scenario():
        async with auth_database(identity_dsn,monkeypatch) as (c,_):
            monkeypatch.setenv('AI_MODE','demo')
            monkeypatch.setattr('api.readiness.rag_ready',lambda:False)
            with TestClient(app) as client:
                sessions=app.state.company_sessions
                @asynccontextmanager
                async def readonly():
                    async with sessions() as s:
                        await s.execute(text('SET TRANSACTION READ ONLY'))
                        yield s
                app.state.company_sessions=readonly
                assert client.get('/ready').status_code==200
                await c.execute('DROP TABLE auth_news_grants')
                assert client.get('/ready').status_code==503
    asyncio.run(scenario())
