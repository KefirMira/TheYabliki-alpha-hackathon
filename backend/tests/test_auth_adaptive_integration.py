"""Synthetic local agent with real PostgreSQL ACL, transactions and no auth overrides."""
import asyncio
import json
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import event
from schemas.financial_review import FinancialReview, FinancialFinding
from services import synthetic_news_execution_service as module
from synthetic_actor_fixture import job_database, add_actor
from test_news_identity_migration import identity_dsn
from test_synthetic_execution_integration import seed, corpus

pytestmark = pytest.mark.integration


def executor(sessions, sdk=None, loader=corpus, token=None):
    return module.SyntheticNewsExecutionService(sessions,corpus_loader=loader,confirm_synthetic=True,
        fake_sdk=sdk,session_token=token or sessions.synthetic_test_token)


@pytest.mark.parametrize('path',['direct','search','repair'])
def test_adaptive_paths_atomic_trace_cache_and_no_connection(identity_dsn,monkeypatch,tmp_path,path):
    async def scenario():
        async with job_database(identity_dsn) as (engine,sessions,c,news):
            await seed(c,news)
            if path=='search':
                await c.execute("UPDATE companies SET industry=NULL WHERE source_id='SYNTH-COMPANY-A'")
            sdk = module.LocalFakeAnalysisSDK()
            active = 0
            def checkout(*args):
                nonlocal active
                active+=1
            def checkin(*args):
                nonlocal active
                active-=1
            event.listen(engine.sync_engine,'checkout',checkout)
            event.listen(engine.sync_engine,'checkin',checkin)
            decide,complete = sdk.decide,sdk.complete
            async def local_decide(obs):
                assert active==0
                return await decide(obs)
            async def local_complete(payload):
                assert active==0
                if path=='repair':
                    return json.dumps({'relevance':'unknown','summary':'Учебная сводка.',
                        'risks':['Кредит компании 987654 рублей под 19,25%.'],
                        'opportunities':[],'recommendations':[]},ensure_ascii=False)
                return await complete(payload)
            sdk.decide=AsyncMock(side_effect=local_decide)
            sdk.complete=AsyncMock(side_effect=local_complete)
            service=executor(sessions,sdk)
            report=await service.analyze_saved('SYNTH-COMPANY-A',news)
            assert report.status=='COMPLETED',report.error_code
            trace=report.orchestration
            assert trace.status=='COMPLETED' and trace.paid_calls==0
            assert trace.decisions<=3 and trace.drafts==1 and trace.searches==(path=='search')
            assert trace.corrections==(path=='repair') and trace.reviews==(2 if path=='repair' else 1)
            stored=json.loads(await c.fetchval('SELECT validation::text FROM company_news_analyses'))
            assert stored['orchestration']==trace.model_dump(mode='json')
            assert stored['passed'] is False
            assert stored['financial_review']['financial_correctness']=='UNKNOWN'
            if path=='repair':
                assert report.result.analysis.risks==[]
                removed=next(e for e in trace.events if e.tool=='REMOVE_CLAIM')
                assert removed.before_sha256!=removed.after_sha256 and removed.field=='risks[0]'
                assert sum(e.tool=='VALIDATE' for e in trace.events)==2
                assert any('FINANCIAL_NUMBER_NOT_IN_INPUT' in e.observation.finding_codes for e in trace.events if e.observation)
                assert '987654' not in trace.model_dump_json()
                (tmp_path/'orchestration.json').write_text(trace.model_dump_json(indent=2),encoding='utf-8')
            old_decisions=sdk.decide.await_count
            cached=await service.analyze_saved('SYNTH-COMPANY-A',news)
            assert cached.status=='REUSED' and cached.orchestration is None
            assert sdk.decide.await_count==old_decisions
            sdk.complete.assert_awaited_once()
            assert await c.fetchval('SELECT count(*) FROM news_analysis_attempts')==1
    asyncio.run(scenario())


@pytest.mark.parametrize('failure',['unknown_tool','no_sources','blocker','override_blocker','bad_field','trace_write','late_blocker','source_tamper','correction_provenance'])
def test_agent_failures_have_no_partial_results(identity_dsn,monkeypatch,failure):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            await seed(c,news)
            sdk=module.LocalFakeAnalysisSDK()
            loader=corpus
            if failure=='no_sources': loader=lambda: []
            if failure=='unknown_tool': sdk.decide=AsyncMock(return_value={'action':'SHELL','reason':'BLOCKER'})
            if failure in {'blocker','override_blocker'}:
                sdk.complete=AsyncMock(return_value=json.dumps({'relevance':'unknown','summary':'Вывод [Источник 999].',
                    'risks':[],'opportunities':[],'recommendations':[]}))
            if failure=='override_blocker':
                original=sdk.decide
                async def override(obs):
                    if obs.stage=='review':return {'action':'KEEP_WITH_WARNINGS','reason':'REVIEW_REQUIRED'}
                    return await original(obs)
                sdk.decide=AsyncMock(side_effect=override)
            if failure=='bad_field':
                original=sdk.decide
                async def override(obs):
                    if obs.stage=='review':return {'action':'REMOVE_CLAIM','reason':'UNSUPPORTED_ITEM','field':'risks[999]'}
                    return await original(obs)
                sdk.decide=AsyncMock(side_effect=override)
            if failure=='trace_write':
                await c.execute("""CREATE FUNCTION reject_trace() RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN IF NEW.validation ? 'orchestration' THEN RAISE EXCEPTION 'synthetic'; END IF; RETURN NEW; END $$;
                    CREATE TRIGGER reject_trace BEFORE INSERT ON company_news_analyses FOR EACH ROW EXECUTE FUNCTION reject_trace()""")
            if failure=='source_tamper':
                await c.execute("UPDATE companies SET industry=NULL WHERE source_id='SYNTH-COMPANY-A'")
                from services import local_adaptive_service
                monkeypatch.setattr(local_adaptive_service,'search_chunks',lambda *args,**kwargs:[
                    dict(source='invented.pdf',page=1,chunk_id=1,text='Invented source',score=1)])
            if failure in {'late_blocker','correction_provenance'}:
                sdk.complete=AsyncMock(return_value=json.dumps({'relevance':'unknown','summary':'Учебная сводка.',
                    'risks':['Стоимость кредитования не меняется.'],'opportunities':[],'recommendations':[]}))
            if failure=='correction_provenance':
                assemble=module.analyze_for_company_with_evidence
                assembles=[]
                async def tamper(*args,**kwargs):
                    bundle=await assemble(*args,**kwargs)
                    assembles.append(1)
                    if len(assembles)==2:bundle.evidence[0].text='Invented after correction'
                    return bundle
                monkeypatch.setattr(module,'analyze_for_company_with_evidence',tamper)
            if failure=='late_blocker':
                reviewer=module.review_financial_analysis
                calls=[]
                def review(*args):
                    calls.append(1)
                    if len(calls)==2:
                        return FinancialReview(status='ERROR',blocking=True,findings=[FinancialFinding(code='SYNTHETIC_BLOCKER',
                            severity='ERROR',disposition='CONFIRMED_ERROR',field='summary',claim='Synthetic',explanation='Synthetic')])
                    return reviewer(*args)
                monkeypatch.setattr(module,'review_financial_analysis',review)
            result=await executor(sessions,sdk,loader).analyze_saved('SYNTH-COMPANY-A',news)
            assert result.status=='FAILED',result.model_dump()
            assert result.orchestration.status=='FAILED'
            if failure=='late_blocker': assert result.orchestration.reviews==2
            if failure=='no_sources': assert result.fake_calls==0
            assert result.paid_calls==0
            assert await c.fetchval('SELECT status FROM analysis_runs')=='FAILED'
            assert await c.fetchval('SELECT response_payload IS NULL FROM news_analysis_attempts')
            for table in ['company_news_analyses','insight_evidence']:
                assert await c.fetchval('SELECT count(*) FROM '+table)==0
    asyncio.run(scenario())


@pytest.mark.parametrize('denial',['membership','grant','expired','revoked','write','no_token'])
def test_actor_acl_before_claim_and_cached_response(identity_dsn,denial):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            await seed(c,news)
            initial=await executor(sessions).analyze_saved('SYNTH-COMPANY-A',news)
            assert initial.status=='COMPLETED'
            companies=() if denial=='membership' else ('SYNTH-COMPANY-A',)
            user,token=await add_actor(c,news,companies,grant=denial!='grant')
            if denial=='expired':
                await c.execute("UPDATE auth_sessions SET created_at=now()-interval '2 hours',expires_at=now()-interval '1 hour' WHERE user_id=$1",user)
            if denial=='revoked':await c.execute('UPDATE auth_sessions SET revoked_at=clock_timestamp() WHERE user_id=$1',user)
            if denial=='write':await c.execute('UPDATE auth_user_companies SET can_analyze=false WHERE user_id=$1',user)
            service=executor(sessions,token=token)
            if denial=='no_token':service.session_token=None
            for target in [news,news+999]:
                report=await service.analyze_saved('SYNTH-COMPANY-A',target)
                assert report.status=='REJECTED' and report.result is None
                assert report.error_code==('AUTHENTICATION_REQUIRED' if denial in {'expired','revoked','no_token'} else 'ACCESS_DENIED')
                assert report.fake_calls==0 and report.orchestration is None
            assert await c.fetchval('SELECT count(*) FROM news_analysis_attempts')==1
    asyncio.run(scenario())
