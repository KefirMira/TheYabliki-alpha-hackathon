import asyncio

import httpx
import pytest
from sqlalchemy import event

from api.company_analyses import get_analysis_service
from main import app
from services.company_analysis_service import CompanyAnalysisService, AnalysisFailure
from repositories.news_analysis_job_repository import AnalysisConflict
from repositories.evidence_repository import EvidenceRepository
from test_job_claim_integration import job_database, identity_dsn

pytestmark = pytest.mark.integration


def test_eight_post_requests_one_paid_call_and_cached_replay(identity_dsn, bundle_factory, monkeypatch):
    monkeypatch.setenv('AI_MODE','full')
    async def scenario():
        async with job_database(identity_dsn) as (engine,sessions,c,news):
            entered, release = asyncio.Event(), asyncio.Event()
            calls, connections = [0], [0]
            event.listen(engine.sync_engine,'checkout',lambda *args: connections.__setitem__(0,connections[0]+1))
            event.listen(engine.sync_engine,'checkin',lambda *args: connections.__setitem__(0,connections[0]-1))
            async def analyzer(*,news,company):
                assert connections[0] == 0
                calls[0] += 1
                entered.set()
                await release.wait()
                assert connections[0] == 0
                return bundle_factory(news=news,company_id=company.company_id)
            app.dependency_overrides[get_analysis_service]=lambda:CompanyAnalysisService(sessions,analyzer)
            try:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                    path=f'/api/companies/SYNTH-COMPANY-A/news/{news}/analyses'
                    first=asyncio.create_task(client.post(path))
                    await asyncio.wait_for(entered.wait(),10)
                    repeats=await asyncio.gather(*(client.post(path) for _ in range(7)))
                    assert all(r.status_code==409 for r in repeats)
                    assert all(r.json()['detail']['code']=='ANALYSIS_ALREADY_RUNNING' for r in repeats)
                    release.set()
                    result=await first
                    assert result.status_code==201
                    # Simulate losing the first HTTP response after commit: retry only the request.
                    replay=await client.post(path)
                    assert replay.status_code==200 and replay.json()==result.json()
                    assert calls[0]==1
                    assert await c.fetchval('SELECT count(*) FROM analysis_runs')==1
                    assert await c.fetchval('SELECT count(*) FROM company_news_analyses')==1
                    assert await c.fetchval('SELECT count(*) FROM insight_evidence')==2
                    assert await c.fetchval('SELECT count(*) FROM news_articles')==1
            finally:
                release.set()
                app.dependency_overrides.pop(get_analysis_service,None)
    asyncio.run(scenario())


@pytest.mark.parametrize('failure',['ai','evidence'])
def test_protected_failure_no_automatic_retry(identity_dsn,bundle_factory,failure):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            calls=[0]
            async def analyzer(**kwargs):
                calls[0]+=1
                if failure=='ai': raise OSError('Synthetic network uncertainty')
                return bundle_factory(news=kwargs['news'])
            class BrokenEvidence(EvidenceRepository):
                async def create(self,*args):
                    await super().create(*args)
                    raise RuntimeError('Synthetic evidence failure')
            service=CompanyAnalysisService(sessions,analyzer,BrokenEvidence)
            with pytest.raises(AnalysisFailure):
                await service.analyze_saved('SYNTH-COMPANY-A',news)
            with pytest.raises(AnalysisConflict,match='ANALYSIS_RETRY_REQUIRED'):
                await service.analyze_saved('SYNTH-COMPANY-A',news)
            assert calls[0]==1
            assert await c.fetchval("SELECT status FROM analysis_runs")=='FAILED'
            assert await c.fetchval('SELECT count(*) FROM company_news_analyses')==0
            assert await c.fetchval('SELECT count(*) FROM insight_evidence')==0
            assert await c.fetchval('SELECT response_payload FROM news_analysis_attempts') is None
    asyncio.run(scenario())
