import asyncio
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import event

from repositories.analysis_run_repository import AnalysisRunRepository
from repositories.company_analysis_repository import CompanyAnalysisRepository
from repositories.evidence_repository import EvidenceRepository
from repositories.news_analysis_job_repository import AnalysisConflict
from services.company_analysis_service import CompanyAnalysisService
from test_job_claim_integration import job_database, identity_dsn

pytestmark=pytest.mark.integration


async def historic_result(sessions,company,news,bundle):
    async with sessions() as s,s.begin():
        run=await AnalysisRunRepository(s).start(company)
        insight=await CompanyAnalysisRepository(s).create(run,company,news,bundle)
        for evidence in bundle.evidence:
            await EvidenceRepository(s).create(insight,evidence)
        await AnalysisRunRepository(s).finish(run,'COMPLETED')
        return run,insight


async def history_snapshot(c):
    return {table:await c.fetchval(f"SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY id),'[]')::text FROM {table} t")
            for table in ('companies','news_articles','analysis_runs','company_news_analyses','insight_evidence')}


def test_register_history_concurrently_preserves_all_old_rows(identity_dsn,bundle_factory):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            company=await c.fetchval("SELECT id FROM companies WHERE source_id='SYNTH-COMPANY-A'")
            bundle=bundle_factory(news='Synthetic saved news')
            run,insight=await historic_result(sessions,company,news,bundle)
            before=await history_snapshot(c)
            async def no_ai(**kwargs):pytest.fail('Historical result must not call AI')
            service=CompanyAnalysisService(sessions,no_ai)
            results=await asyncio.gather(*(service.analyze_saved('SYNTH-COMPANY-A',news) for _ in range(8)))
            assert all(r.reused and r.run_id==run and r.insight_id==insight for r in results)
            assert results[0].cached_response.analysis==bundle.analysis
            assert await history_snapshot(c)==before
            assert await c.fetchval('SELECT count(*) FROM news_analysis_attempts')==1
    asyncio.run(scenario())


@pytest.mark.parametrize('case',['multiple','invalid_payload','null_run_company'])
def test_ambiguous_history_is_diagnostic_not_repaired(identity_dsn,bundle_factory,case):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            company=await c.fetchval("SELECT id FROM companies WHERE source_id='SYNTH-COMPANY-A'")
            run,_=await historic_result(sessions,company,news,bundle_factory(news='Synthetic saved news'))
            if case=='multiple':await historic_result(sessions,company,news,bundle_factory(news='Synthetic saved news'))
            elif case=='invalid_payload':await c.execute("UPDATE company_news_analyses SET validation='{}'")
            else:await c.execute('UPDATE analysis_runs SET company_id=NULL WHERE id=$1',run)
            before=await history_snapshot(c)
            async def no_ai(**kwargs):pytest.fail('Ambiguous history must not call AI')
            with pytest.raises(AnalysisConflict,match='HISTORY_'):
                await CompanyAnalysisService(sessions,no_ai).analyze_saved('SYNTH-COMPANY-A',news)
            assert await history_snapshot(c)==before
            assert await c.fetchval('SELECT count(*) FROM news_analysis_attempts')==0
    asyncio.run(scenario())


@pytest.mark.parametrize('status',['RUNNING','FAILED'])
@pytest.mark.parametrize('null_company',[False,True])
def test_unlinked_legacy_run_blocks_new_paid_claim(identity_dsn,status,null_company):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            await c.execute("INSERT INTO analysis_runs(company_id,analysis_type,status) SELECT id,'NEWS',$1 FROM companies WHERE source_id='SYNTH-COMPANY-A'",status)
            if null_company:
                await c.execute('UPDATE analysis_runs SET company_id=NULL')
            async def no_ai(**kwargs):pytest.fail('Cannot infer legacy news_id')
            with pytest.raises(AnalysisConflict,match='LEGACY_RUN_REVIEW_REQUIRED'):
                await CompanyAnalysisService(sessions,no_ai).analyze_saved('SYNTH-COMPANY-A',news)
            assert await c.fetchval('SELECT count(*) FROM analysis_runs')==1
    asyncio.run(scenario())


@pytest.mark.parametrize('phase',['claim','result'])
def test_commit_acknowledgement_loss_never_spends_twice(identity_dsn,bundle_factory,phase):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            calls=[0]
            lost=[False]
            @asynccontextmanager
            async def unreliable_sessions():
                async with sessions() as s:
                    def after_commit(sync_session):
                        should_fail = calls[0]==0 if phase=='claim' else calls[0]==1
                        if should_fail and not lost[0]:
                            lost[0]=True
                            raise OSError('Synthetic commit acknowledgement lost')
                    event.listen(s.sync_session,'after_commit',after_commit)
                    yield s
            async def analyzer(**kwargs):
                calls[0]+=1
                return bundle_factory(news=kwargs['news'])
            service=CompanyAnalysisService(unreliable_sessions,analyzer)
            if phase=='claim':
                with pytest.raises(OSError):await service.analyze_saved('SYNTH-COMPANY-A',news)
                with pytest.raises(AnalysisConflict,match='ALREADY_RUNNING'):
                    await service.analyze_saved('SYNTH-COMPANY-A',news)
                assert calls[0]==0
            else:
                result=await service.analyze_saved('SYNTH-COMPANY-A',news)
                replay=await service.analyze_saved('SYNTH-COMPANY-A',news)
                assert replay.reused and replay.run_id==result.run_id
                assert calls[0]==1
                assert await c.fetchval('SELECT status FROM analysis_runs')=='COMPLETED'
            assert lost[0]
            assert await c.fetchval('SELECT count(*) FROM analysis_runs')==1
    asyncio.run(scenario())


def test_two_companies_can_call_ai_concurrently(identity_dsn,bundle_factory):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            barrier=asyncio.Barrier(2)
            async def analyzer(**kwargs):
                await asyncio.wait_for(barrier.wait(),10)
                return bundle_factory(news=kwargs['news'],company_id=kwargs['company'].company_id)
            service=CompanyAnalysisService(sessions,analyzer)
            results=await asyncio.gather(*(service.analyze_saved(source,news) for source in ('SYNTH-COMPANY-A','SYNTH-COMPANY-B')))
            assert results[0].run_id!=results[1].run_id
            assert await c.fetchval('SELECT count(*) FROM news_articles')==1
            assert await c.fetchval('SELECT count(*) FROM company_news_analyses')==2
    asyncio.run(scenario())
