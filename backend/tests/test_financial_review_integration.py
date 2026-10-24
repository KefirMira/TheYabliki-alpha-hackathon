import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from services import synthetic_news_execution_service as module
from services.company_analysis_service import CompanyAnalysisService
from services.insight_service import InsightService
from test_job_claim_integration import job_database
from test_news_identity_migration import identity_dsn

pytestmark = pytest.mark.integration


def corpus():
    return [dict(source='synthetic-gold.pdf', page=2, chunk_id=4,
        text='Учебная аналитика: обзор золота. Ключевая ставка и кредитные договоры конкретной компании не рассматриваются.')]


def executor(sessions, summary):
    sdk = module.LocalFakeAnalysisSDK()
    sdk.complete = AsyncMock(return_value=json.dumps(dict(relevance='unknown', summary=summary,
        risks=[], opportunities=[], recommendations=[]), ensure_ascii=False))
    return module.SyntheticNewsExecutionService(sessions, corpus_loader=corpus,
        confirm_synthetic=True, fake_sdk=sdk), sdk


@pytest.mark.parametrize('summary,status,expected_code', [
    ('Если у компании есть кредит, возможно влияние ставки; условия договора неизвестны.', 'UNKNOWN', 'CREDIT_TERMS_UNKNOWN'),
    ('Стоимость кредитования не меняется.', 'NEEDS_REVIEW', 'UNSUPPORTED_UNCHANGED_BORROWING_COST'),
    ('Кредит компании 987654 рублей под 19,25% на 36 месяцев.', 'NEEDS_REVIEW', 'FINANCIAL_NUMBER_NOT_IN_INPUT'),
    ('Возможно влияние на кредит компании [Источник 1].', 'UNKNOWN', 'CITATION_ENTAILMENT_UNKNOWN'),
])
def test_findings_saved_atomically_visible_in_existing_card_without_revalidation(identity_dsn, monkeypatch, summary, status, expected_code):
    async def scenario():
        async with job_database(identity_dsn) as (_, sessions, connection, news):
            await connection.execute("UPDATE news_articles SET content='Учебная новость: ключевая ставка' WHERE id=$1", news)
            service, sdk = executor(sessions, summary)
            report = await service.analyze_saved('SYNTH-COMPANY-A', news)
            assert report.status == 'COMPLETED', report.error_code
            assert report.financial_review.status == status
            assert expected_code in {f.code for f in report.financial_review.findings}
            assert report.financial_review.financial_correctness == 'UNKNOWN'
            stored = json.loads(await connection.fetchval('SELECT validation::text FROM company_news_analyses'))
            assert stored['financial_review'] == report.financial_review.model_dump(mode='json')
            assert stored['passed'] is False
            assert 'FINANCIAL_CORRECTNESS_NOT_ESTABLISHED' in stored['warnings']
            assert expected_code in stored['warnings']
            async with sessions() as session:
                card = await InsightService(session).card('SYNTH-COMPANY-A', report.result.insight_id)
            assert card.summary == summary
            assert card.validation['financial_review'] == stored['financial_review']
            assert card.evidence[0].text == corpus()[0]['text']
            response = json.loads(await connection.fetchval('SELECT response_payload::text FROM news_analysis_attempts'))
            assert set(response['analysis']['validation']) == {'passed', 'warnings'}
            assert response == report.result.model_dump(mode='json')
            monkeypatch.setattr(module, 'review_financial_analysis', lambda *a: pytest.fail('Cache revalidated'))
            sdk.complete.side_effect = AssertionError('Cache generated again')
            cached = await service.analyze_saved('SYNTH-COMPANY-A', news)
            assert cached.status == 'REUSED' and cached.fake_calls == 0
            assert cached.financial_review is None  # Retrieve the stored review via existing detail/card.
            assert cached.result == report.result
            sdk.complete.assert_awaited_once()
            assert await connection.fetchval('SELECT count(*) FROM analysis_runs') == 1
            assert json.loads(await connection.fetchval('SELECT validation::text FROM company_news_analyses')) == stored
    asyncio.run(scenario())


@pytest.mark.parametrize('failure', ['checker_error', 'missing_reference'])
def test_review_failure_has_no_partial_persistence_or_automatic_retry(identity_dsn, monkeypatch, failure):
    async def scenario():
        async with job_database(identity_dsn) as (_, sessions, connection, news):
            await connection.execute("UPDATE news_articles SET content='Учебная ключевая ставка' WHERE id=$1", news)
            service, sdk = executor(sessions, 'Возможное влияние [Источник 999].')
            if failure == 'checker_error':
                def broken(*args):
                    raise RuntimeError('PRIVATE-REVIEW-DETAILS')
                monkeypatch.setattr(module, 'review_financial_analysis', broken)
            report = await service.analyze_saved('SYNTH-COMPANY-A', news)
            assert report.status == 'FAILED' and report.result is None
            assert 'PRIVATE-' not in report.model_dump_json()
            if failure == 'missing_reference':
                assert report.error_code == 'FINANCIAL_REVIEW_BLOCKED'
                assert report.financial_review.blocking
                assert report.financial_review.findings[0].disposition == 'CONFIRMED_ERROR'
            assert next(step for step in report.steps if step.tool == 'financial_review').status == 'FAILED'
            assert await connection.fetchval('SELECT status FROM analysis_runs') == 'FAILED'
            assert await connection.fetchval('SELECT retry_policy FROM news_analysis_attempts') == 'REVIEW_REQUIRED'
            assert await connection.fetchval('SELECT response_payload IS NULL AND insight_id IS NULL FROM news_analysis_attempts')
            for table in ['company_news_analyses', 'insight_evidence']:
                assert await connection.fetchval('SELECT count(*) FROM '+table) == 0
            repeated = await service.analyze_saved('SYNTH-COMPANY-A', news)
            assert repeated.status == 'CONFLICT' and repeated.error_code == 'ANALYSIS_RETRY_REQUIRED'
            sdk.complete.assert_awaited_once()
    asyncio.run(scenario())


def test_legacy_validation_storage_does_not_change(identity_dsn, bundle_factory):
    async def scenario():
        async with job_database(identity_dsn) as (_, sessions, connection, news):
            async def legacy(*, news, company):
                bundle = bundle_factory(news, company.company_id)
                bundle.analysis.validation.passed = True
                bundle.analysis.validation.warnings = []
                return bundle
            saved = await CompanyAnalysisService(sessions, legacy).analyze_saved('SYNTH-COMPANY-A', news)
            stored = json.loads(await connection.fetchval('SELECT validation::text FROM company_news_analyses'))
            assert stored == {'passed': True, 'warnings': []}
            assert saved.result.financial_review is None  # Legacy passed is not a financial assessment.
    asyncio.run(scenario())
