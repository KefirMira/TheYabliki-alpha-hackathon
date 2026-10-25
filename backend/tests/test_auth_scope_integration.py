import asyncio
import json
from unittest.mock import AsyncMock
import pytest
from synthetic_actor_fixture import job_database
from test_news_identity_migration import identity_dsn
from test_synthetic_execution_integration import corpus,seed
from services.synthetic_news_execution_service import SyntheticNewsExecutionService,LocalFakeAnalysisSDK
from services.local_adaptive_service import CORRECTABLE

pytestmark=pytest.mark.integration


@pytest.mark.parametrize('claim,code',[
    ('Покупайте инструмент: доход обеспечен при любых условиях.','UNCONDITIONAL_FINANCIAL_OUTCOME'),
    ('График погашения согласован [Источник 1].','CONTRACT_FACT_GROUNDING_REQUIRED'),
    ('«Стоимость кредитования не меняется».','CLAIM_SCOPE_UNRESOLVED')])
def test_new_review_signals_do_not_expand_correction_and_preserve_atomic_cache(identity_dsn,claim,code):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            await seed(c,news)
            sdk=LocalFakeAnalysisSDK()
            sdk.complete=AsyncMock(return_value=json.dumps(dict(relevance='unknown',summary='Синтетическая сводка.',
                risks=[claim],opportunities=[],recommendations=[]),ensure_ascii=False))
            service=SyntheticNewsExecutionService(sessions,corpus_loader=corpus,confirm_synthetic=True,
                fake_sdk=sdk,session_token=sessions.synthetic_test_token)
            report=await service.analyze_saved('SYNTH-COMPANY-A',news)
            assert report.status=='COMPLETED',report.error_code
            assert code not in CORRECTABLE
            assert report.result.analysis.risks==[claim] and report.orchestration.corrections==0
            assert any(f.code==code for f in report.financial_review.findings)
            stored=json.loads(await c.fetchval('SELECT validation::text FROM company_news_analyses'))
            assert stored['financial_review']==report.financial_review.model_dump(mode='json')
            assert stored['orchestration']==report.orchestration.model_dump(mode='json')
            assert stored['passed'] is False and stored['financial_review']['financial_correctness']=='UNKNOWN'
            repeated=await service.analyze_saved('SYNTH-COMPANY-A',news)
            assert repeated.status=='REUSED' and repeated.result==report.result
            sdk.complete.assert_awaited_once()
            assert await c.fetchval('SELECT count(*) FROM news_analysis_attempts')==1
    asyncio.run(scenario())
