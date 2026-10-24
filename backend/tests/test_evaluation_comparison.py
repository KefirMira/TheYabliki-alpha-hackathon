import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from evaluation import comparison
from evaluation.financial_checks import financial_assertion_flags
from evaluation.runner import technical_checks, validate_real_plan
from evaluation.scenarios import scenarios


@pytest.mark.parametrize('text',[
    'Стоимость кредитования не меняется.',
    'Стоимость кредита компании останется прежней.',
    'Кредитные ставки не изменятся.',
    'Процентные расходы не изменятся.',
    'Ставка сохранена: стоимость кредитования не меняется, но и не снижается. Условия кредита неизвестны.',
])
def test_evaluation_detects_unqualified_financial_invariance(text):
    assert 'UNSUPPORTED_UNCHANGED_BORROWING_COST' in financial_assertion_flags(text)


@pytest.mark.parametrize('text',[
    'Если договор это предусматривает, стоимость кредита может не меняться.',
    'Нельзя утверждать, что стоимость кредитования не меняется.',
    'Сохранение ставки не гарантирует, что стоимость кредитования не изменится.',
    'Стоимость кредита зависит от договора; условия компании неизвестны.',
])
def test_evaluation_does_not_flag_explicitly_qualified_statements(text):
    assert 'UNSUPPORTED_UNCHANGED_BORROWING_COST' not in financial_assertion_flags(text)


def test_evaluation_checks_flag_but_never_certify_financial_truth():
    raw=json.dumps({'relevance':'medium','summary':'Стоимость кредитования не меняется.',
        'risks':['Расходы составят 10 млн рублей.'],'opportunities':[],'recommendations':[]})
    checks=technical_checks(raw,[{'id':1}],scenarios()[0],'stop')
    assert checks['schema_valid'] and checks['factual_accuracy']=='NOT_ASSESSED'
    assert set(checks['financial_assertion_flags'])=={
        'UNSUPPORTED_UNCHANGED_BORROWING_COST','FINANCIAL_NUMBER_REQUIRES_SOURCE_REVIEW'}
    assert checks['human_review_required']


def test_comparison_plan_profiles_differ_but_news_and_rag_identical():
    prepared,plan=comparison.comparison_plan()
    a,b=prepared
    assert a[0]['news']==b[0]['news']==scenarios()[0]['news']
    assert a[1]['evidence']==b[1]['evidence']
    assert a[1]['evidence'][0]['document']=='synthetic-evaluation.txt'
    assert a[0]['company']['loan_product_flag'] is True
    assert b[0]['company']['loan_product_flag'] is False
    assert a[0]['company']['industry']!=b[0]['company']['industry']
    for case,request in prepared:
        assert case['company']['revenue'] is case['company']['credit_exposure'] is None
        assert 'business_features' in request['messages'][1]['content']
        assert 'loan_product_flag' in request['messages'][1]['content']
        assert 'не доказывает наличие долга' in request['messages'][1]['content']
        assert request['input_token_planning_bound']<=8000
    assert plan['planned_requests']==2 and plan['limits']['max_requests']==2
    assert plan['estimated_upper_usd'] is None and plan['total_output_token_limit']==2000
    assert plan['execution_available']=='EXPLICIT_ORGANIZER_PAIR_ONLY'
    validate_real_plan(plan)
    # The separate pair policy does not weaken the original single-call policy.
    plan['limits']['billing_mode']='organizer_rub_quota'
    with pytest.raises(ValueError,match='INVALID_ORGANIZER_LIMITS'):validate_real_plan(plan)


@pytest.mark.parametrize('args',[['--real'],['--rag-dir','private'],['--max-requests','3']])
def test_comparison_cli_cannot_send_real_or_load_private_data(args):
    with pytest.raises(SystemExit):comparison.main(args)


def test_comparison_plan_never_calls_sdk_or_creates_results(tmp_path,capsys):
    complete=AsyncMock(side_effect=AssertionError('No SDK in plan'))
    assert asyncio.run(comparison.execute(SimpleNamespace(plan=True),complete=complete,root=tmp_path))==0
    complete.assert_not_called()
    assert not list(tmp_path.iterdir())
    assert json.loads(capsys.readouterr().out)['plan']['planned_requests']==2


def test_comparison_end_to_end_with_fake_sdk(tmp_path):
    calls=[]
    async def create(**kwargs):
        calls.append(kwargs)
        text=kwargs['messages'][1]['content']
        fuel='Оптовая торговля топливом' in text
        response={'relevance':'medium',
            'summary':'Возможно влияние на финансирование запасов топлива [Источник 1].' if fuel
                      else 'Возможно влияние на оплату этапов проекта и расходы на персонал [Источник 1].',
            'risks':['Проверить расчёты после отгрузки.' if fuel else 'Проверить сроки приёмки этапов.'],
            'opportunities':['Планирование запасов.' if fuel else 'Планирование проектной команды.'],
            'recommendations':['Уточнить условия; долг и процентные расходы неизвестны.']}
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(response,ensure_ascii=False)),finish_reason='stop')])
    fake_sdk=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(side_effect=create))))
    async def complete(messages,*,max_tokens,timeout):
        assert max_tokens==1000 and 0<timeout<=60
        response=await fake_sdk.chat.completions.create(model='fake-no-llm',messages=messages,max_tokens=max_tokens)
        return {'raw':response.choices[0].message.content,'finish_reason':response.choices[0].finish_reason,
                'model':'fake-no-llm','usage':None}
    assert asyncio.run(comparison.execute(SimpleNamespace(plan=False),complete=complete,root=tmp_path))==0
    assert fake_sdk.chat.completions.create.await_count==2
    assert calls[0]['messages'][1]['content']!=calls[1]['messages'][1]['content']
    folder=next(tmp_path.iterdir())
    report=json.loads((folder/'comparison.json').read_text(encoding='utf-8'))
    assert report['quality_score'] is None and set(report['criteria'].values())=={'NOT_ASSESSED'}
    assert not report['pair']['risks']['identical']
    assert (folder/'comparison-review.tsv').exists()
    for item in report['profiles'].values():
        assert item['lexical_feature_mentions'] and item['technical_checks']['citation_ids_valid']
        assert item['technical_checks']['financial_assertion_flags']==[]


def test_comparison_default_fake_identical_answers_are_not_successful_personalization(tmp_path):
    assert asyncio.run(comparison.execute(SimpleNamespace(plan=False),root=tmp_path))==0
    report=json.loads((next(tmp_path.iterdir())/'comparison.json').read_text(encoding='utf-8'))
    assert report['pair']['risks']['identical']
    assert report['pair']['summary']['identical']
    assert report['quality_score'] is None
    assert all(not p['lexical_feature_mentions'] for p in report['profiles'].values())
