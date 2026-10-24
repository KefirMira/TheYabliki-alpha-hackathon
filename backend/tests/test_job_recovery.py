import asyncio
from types import SimpleNamespace

import pytest

from analysis_admin import arguments, execute
from repositories.news_analysis_job_repository import AnalysisConflict
from services.company_analysis_service import CompanyAnalysisService, AnalysisFailure
from test_job_claim_integration import job_database, identity_dsn

pytestmark=pytest.mark.integration


async def admin(sessions,action,news,run,confirm=True):
    return await execute(SimpleNamespace(action=action,company_source_id='SYNTH-COMPANY-A',
        news_id=news,run_id=run,actor='synthetic-operator',reason='Synthetic controlled recovery',
        confirm_worker_stopped=confirm,confirm_provider_finished=confirm),sessions)


def test_manual_retry_concurrency_and_attempt_limit(identity_dsn,bundle_factory):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            calls=[0]
            entered,release=asyncio.Event(),asyncio.Event()
            async def analyzer(**kwargs):
                calls[0]+=1
                if calls[0]==1:raise OSError('Synthetic uncertain transport')
                entered.set()
                await release.wait()
                raise RuntimeError('Synthetic second failed attempt')
            service=CompanyAnalysisService(sessions,analyzer)
            with pytest.raises(AnalysisFailure):await service.analyze_saved('SYNTH-COMPANY-A',news)
            first=await c.fetchval('SELECT id FROM analysis_runs')
            with pytest.raises(AnalysisConflict,match='ATTESTATION'):
                await admin(sessions,'approve-retry',news,first,False)
            await admin(sessions,'approve-retry',news,first)
            second=asyncio.create_task(service.analyze_saved('SYNTH-COMPANY-A',news))
            await asyncio.wait_for(entered.wait(),10)
            with pytest.raises(AnalysisConflict,match='ALREADY_RUNNING'):
                await service.analyze_saved('SYNTH-COMPANY-A',news)
            release.set()
            with pytest.raises(AnalysisFailure):await second
            latest=await c.fetchval('SELECT max(id) FROM analysis_runs')
            with pytest.raises(AnalysisConflict,match='LIMIT_REACHED'):
                await admin(sessions,'approve-retry',news,latest)
            with pytest.raises(AnalysisConflict,match='LIMIT_REACHED'):
                await service.analyze_saved('SYNTH-COMPANY-A',news)
            assert calls[0]==2
            assert await c.fetchval('SELECT count(*) FROM news_analysis_attempts')==2
    asyncio.run(scenario())


def test_stalled_readonly_inspection_and_late_result_fenced(identity_dsn,bundle_factory):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            entered,release=asyncio.Event(),asyncio.Event()
            async def analyzer(**kwargs):
                entered.set()
                await release.wait()
                return bundle_factory(news=kwargs['news'])
            service=CompanyAnalysisService(sessions,analyzer)
            pending=asyncio.create_task(service.analyze_saved('SYNTH-COMPANY-A',news))
            await asyncio.wait_for(entered.wait(),10)
            # Set both timestamps coherently; never weaken the migration CHECK.
            await c.execute("UPDATE news_analysis_attempts SET reserved_at=now()-interval '10 minutes', deadline_at=now()-interval '5 minutes'")
            stalled=await execute(SimpleNamespace(action='inspect'),sessions)
            assert len(stalled)==1 and stalled[0]['status']=='RUNNING'
            run=stalled[0]['run_id']
            with pytest.raises(AnalysisConflict,match='REVIEW_REQUIRED'):
                await service.analyze_saved('SYNTH-COMPANY-A',news)
            await admin(sessions,'close',news,run)
            release.set()
            with pytest.raises(AnalysisConflict,match='ATTEMPT_CLOSED'):await pending
            assert await c.fetchval('SELECT count(*) FROM company_news_analyses')==0
            assert await c.fetchval('SELECT status FROM analysis_runs')=='FAILED'
            assert await c.fetchval('SELECT response_payload FROM news_analysis_attempts') is None
    asyncio.run(scenario())


def test_protected_timeout_blocks_retry(identity_dsn,monkeypatch):
    monkeypatch.setattr('services.protected_ai.PROTECTED_TIMEOUT_SECONDS',0.01)
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            async def analyzer(**kwargs):await asyncio.sleep(1)
            service=CompanyAnalysisService(sessions,analyzer)
            with pytest.raises(AnalysisFailure):await service.analyze_saved('SYNTH-COMPANY-A',news)
            assert await c.fetchval('SELECT retry_policy FROM news_analysis_attempts')=='REVIEW_REQUIRED'
            with pytest.raises(AnalysisConflict):await service.analyze_saved('SYNTH-COMPANY-A',news)
    asyncio.run(scenario())


@pytest.mark.parametrize('action',['close','approve-retry'])
def test_admin_cli_requires_explicit_attestation(action):
    with pytest.raises(SystemExit):arguments([action])
