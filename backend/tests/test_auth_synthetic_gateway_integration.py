"""Real PostgreSQL isolation/ACL/jobs with an injected local SDK; no external transport."""
import asyncio
import json
import pytest
from sqlalchemy import event
from synthetic_actor_fixture import job_database,add_actor
from test_news_identity_migration import identity_dsn
from repositories.evidence_repository import EvidenceRepository
from services.synthetic_draft_adapter import SyntheticDraftAdapter,DraftLimits
from services.synthetic_gateway_execution_service import SyntheticGatewayExecutionService
from services.synthetic_gateway_input import fixture
from repositories.news_analysis_job_repository import NewsAnalysisJobRepository
from services.company_analysis_service import CompanyAnalysisService
from services.company_context_service import CompanyContextExternalTransferBlocked
from synthetic_gateway_fixture import FakeClient,response

pytestmark=pytest.mark.integration


async def seed(c,news):
    data=fixture()
    await c.execute("UPDATE companies SET source_id=$1,name='DB_PRIVATE_MARKER',industry='DB_PRIVATE_MARKER' WHERE source_id='SYNTH-COMPANY-A'",data['source_id'])
    await c.execute("UPDATE news_articles SET content=$1,title='DB_PRIVATE_MARKER' WHERE id=$2",data['news'],news)


def executor(sessions,client,token=None,limits=None):
    return SyntheticGatewayExecutionService(sessions,draft_adapter=SyntheticDraftAdapter(client,limits=limits),
        session_token=token or sessions.synthetic_test_token)


def test_success_cache_trace_and_no_db_connection_or_db_payload(identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (engine,sessions,c,news):
            await seed(c,news)
            active=0
            def checkout(*args):
                nonlocal active
                active+=1
            def checkin(*args):
                nonlocal active
                active-=1
            event.listen(engine.sync_engine,'checkout',checkout)
            event.listen(engine.sync_engine,'checkin',checkin)
            async def fake(kwargs):
                assert active==0
                messages=json.dumps(kwargs['messages'],ensure_ascii=False)
                assert 'DB_PRIVATE_MARKER' not in messages
                assert 'source_data' not in messages and 'news_from_db' not in messages
                assert fixture()['news'] in messages
                assert 'Синтетическое производство' in messages
                return response()
            client=FakeClient(callback=fake)
            service=executor(sessions,client)
            report=await service.analyze_saved(fixture()['source_id'],news)
            assert report.status=='COMPLETED',report.error_code
            assert report.mode=='synthetic-gateway-only' and report.preparation is None
            trace=report.orchestration
            assert trace.sdk_requests==1 and trace.paid_calls==0 and trace.transport=='fake'
            assert trace.request_outcome=='RESPONSE_VALIDATED' and trace.usage['reasoning_tokens']==500
            assert trace.drafts==1 and trace.decisions<=3 and trace.reviews>=1
            assert next(e.reason for e in trace.events if e.tool=='DRAFT')=='SYNTHETIC_SDK_COMPLETED'
            assert 'DB_PRIVATE_MARKER' not in trace.model_dump_json()
            stored=json.loads(await c.fetchval('SELECT validation::text FROM company_news_analyses'))
            assert stored['orchestration']==trace.model_dump(mode='json')
            assert stored['financial_review']['financial_correctness']=='UNKNOWN' and stored['passed'] is False
            cached=await service.analyze_saved(fixture()['source_id'],news)
            assert cached.status=='REUSED' and cached.result==report.result
            assert len(client.calls)==1 and await c.fetchval('SELECT count(*) FROM news_analysis_attempts')==1
    asyncio.run(scenario())


@pytest.mark.parametrize('failure',['network','timeout','usage','json','length','citation','evidence_write','trace_write','input_limit','changed_news'])
def test_failure_atomicity_no_retry_safe_trace(identity_dsn,failure):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            await seed(c,news)
            value=response()
            if failure=='network':value=OSError('DB_PRIVATE_MARKER')
            if failure=='timeout':value=TimeoutError('DB_PRIVATE_MARKER')
            if failure=='usage':value['usage']=None
            if failure=='json':value['choices'][0]['message']['content']='{'
            if failure=='length':value['choices'][0]['finish_reason']='length'
            if failure=='citation':
                raw=json.loads(value['choices'][0]['message']['content']);raw['summary']='Тезис [Источник 999].'
                value['choices'][0]['message']['content']=json.dumps(raw)
            if failure=='changed_news':await c.execute("UPDATE news_articles SET content='DB_PRIVATE_MARKER' WHERE id=$1",news)
            if failure=='trace_write':
                await c.execute("""CREATE FUNCTION reject_gateway_trace() RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN IF NEW.validation ? 'orchestration' THEN RAISE EXCEPTION 'synthetic'; END IF; RETURN NEW; END $$;
                    CREATE TRIGGER reject_gateway_trace BEFORE INSERT ON company_news_analyses FOR EACH ROW EXECUTE FUNCTION reject_gateway_trace()""")
            client=FakeClient(value)
            service=executor(sessions,client,limits=DraftLimits(max_input_tokens=1) if failure=='input_limit' else None)
            if failure=='evidence_write':
                class RejectEvidence(EvidenceRepository):
                    async def create(self,*args):raise RuntimeError('DB_PRIVATE_MARKER')
                service.evidence_repository=RejectEvidence
            report=await service.analyze_saved(fixture()['source_id'],news)
            assert report.status=='FAILED',report.model_dump()
            assert 'DB_PRIVATE_MARKER' not in report.model_dump_json()
            assert len(client.calls)==(0 if failure in {'input_limit','changed_news'} else 1)
            assert await c.fetchval('SELECT status FROM analysis_runs')=='FAILED'
            assert await c.fetchval('SELECT retry_policy FROM news_analysis_attempts')=='REVIEW_REQUIRED'
            assert await c.fetchval('SELECT response_payload IS NULL FROM news_analysis_attempts')
            for table in ('company_news_analyses','insight_evidence'):
                assert await c.fetchval('SELECT count(*) FROM '+table)==0
            again=await service.analyze_saved(fixture()['source_id'],news)
            assert again.status=='CONFLICT' and len(client.calls)<=1
    asyncio.run(scenario())


def test_eight_concurrent_connections_one_attempt_and_request(identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            await seed(c,news)
            entered,release=asyncio.Event(),asyncio.Event()
            async def fake(kwargs):
                entered.set()
                await release.wait()
                return response()
            client=FakeClient(callback=fake)
            service=executor(sessions,client)
            first=asyncio.create_task(service.analyze_saved(fixture()['source_id'],news))
            await asyncio.wait_for(entered.wait(),10)
            rest=await asyncio.gather(*(service.analyze_saved(fixture()['source_id'],news) for _ in range(7)))
            release.set()
            result=await first
            assert result.status=='COMPLETED' and all(r.status=='CONFLICT' for r in rest)
            assert len(client.calls)==1 and await c.fetchval('SELECT count(*) FROM news_analysis_attempts')==1
    asyncio.run(scenario())


@pytest.mark.parametrize('denial',['company','news','write','revoked'])
def test_real_acl_before_cache_or_claim(identity_dsn,denial):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            await seed(c,news)
            user,token=await add_actor(c,news,(fixture()['source_id'],),grant=denial!='news')
            if denial=='company':await c.execute('DELETE FROM auth_user_companies WHERE user_id=$1',user)
            if denial=='write':await c.execute('UPDATE auth_user_companies SET can_analyze=false WHERE user_id=$1',user)
            if denial=='revoked':await c.execute('UPDATE auth_sessions SET revoked_at=now() WHERE user_id=$1',user)
            client=FakeClient()
            denied=executor(sessions,client,token)
            for cached in (False,True):
                report=await denied.analyze_saved(fixture()['source_id'],news)
                assert report.status=='REJECTED' and report.result is None and client.calls==[]
                if not cached:
                    allowed=await executor(sessions,FakeClient()).analyze_saved(fixture()['source_id'],news)
                    assert allowed.status=='COMPLETED'
            assert await c.fetchval('SELECT count(*) FROM news_analysis_attempts')==1
    asyncio.run(scenario())


def test_ordinary_external_guard_stays_blocked(identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            await seed(c,news)
            with pytest.raises(CompanyContextExternalTransferBlocked):
                await CompanyAnalysisService(sessions).analyze_saved(fixture()['source_id'],news)
            assert await c.fetchval('SELECT count(*) FROM news_analysis_attempts')==0
    asyncio.run(scenario())


@pytest.mark.parametrize('path',['repair','late_close','lost_commit','declared_organizer'])
def test_fencing_recheck_accounting_and_commit_ack(identity_dsn,monkeypatch,path):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            await seed(c,news)
            async def fake(kwargs):
                value=response()
                if path=='repair':
                    data=json.loads(value['choices'][0]['message']['content'])
                    data['risks']=['Стоимость кредитования не меняется.']
                    value['choices'][0]['message']['content']=json.dumps(data,ensure_ascii=False)
                if path=='late_close':
                    row=await c.fetchrow('SELECT company_id,run_id FROM news_analysis_attempts')
                    async with sessions() as s,s.begin():
                        await NewsAnalysisJobRepository(s).administer(row['company_id'],news,row['run_id'],
                            'close','synthetic-operator','synthetic-fencing-test',worker_stopped=True,provider_finished=True)
                return value
            client=FakeClient(callback=fake)
            service=executor(sessions,client)
            lost=[False]
            if path=='declared_organizer':
                import sys
                from types import SimpleNamespace
                monkeypatch.setenv('AI_MODE','full')
                monkeypatch.setitem(sys.modules,'openai',SimpleNamespace(AsyncOpenAI=lambda **kw:client,
                    DefaultAsyncHttpxClient=lambda **kw:None))
                adapter=SyntheticDraftAdapter.organizer(api_key='synthetic-not-real',allow_real=True,acknowledge_unknown_cost=True)
                service=SyntheticGatewayExecutionService(sessions,draft_adapter=adapter,session_token=sessions.synthetic_test_token)
            if path=='lost_commit':
                from contextlib import asynccontextmanager
                @asynccontextmanager
                async def unreliable():
                    async with sessions() as s:
                        def after_commit(sync_session):
                            if len(client.calls)==1 and not lost[0]:
                                lost[0]=True
                                raise OSError('synthetic-lost-ack')
                        event.listen(s.sync_session,'after_commit',after_commit)
                        yield s
                unreliable.kw=sessions.kw
                service.sessions=unreliable
            report=await service.analyze_saved(fixture()['source_id'],news)
            assert len(client.calls)==1
            if path=='late_close':
                assert report.status=='CONFLICT'
                assert await c.fetchval('SELECT count(*) FROM company_news_analyses')==0
                assert await c.fetchval('SELECT status FROM analysis_runs')=='FAILED'
            else:
                assert report.status=='COMPLETED',report.error_code
                if path=='repair':
                    assert report.orchestration.corrections==1 and report.orchestration.reviews==2
                    assert report.result.analysis.risks==[]
                if path=='declared_organizer':
                    assert report.orchestration.transport=='organizer' and report.orchestration.paid_calls==1
                    stored=json.loads(await c.fetchval('SELECT validation::text FROM company_news_analyses'))
                    assert stored['orchestration']['paid_calls']==1
                if path=='lost_commit':assert lost[0]
                cached=await service.analyze_saved(fixture()['source_id'],news)
                assert cached.status=='REUSED' and len(client.calls)==1
    asyncio.run(scenario())
