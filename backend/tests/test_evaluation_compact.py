import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from evaluation import comparison
from evaluation.compact import RULES, VARIANT, output_checks
from evaluation.financial_checks import financial_assertion_flags
from evaluation.runner import technical_checks
from evaluation.__main__ import complete_with_client
from schemas.analysis import AnalysisContent


@pytest.mark.parametrize('text',[
    'Стоимость кредитования не меняется.',
    'Прямого изменения стоимости заёмного финансирования не произошло.',
    'Изменения стоимости заемных средств не было.',
    'Стоимость заёмного финансирования осталась прежней.',
    'Кредитные ставки остаются на прежнем уровне.',
    'Не произошло изменения стоимости кредитования.',
    'Не наблюдается изменений стоимости кредита.',
    'Стоимость кредита компании не изменилась. Если есть долг, условия неизвестны.',
])
def test_evaluation_financial_paraphrases_require_expert_review(text):
    assert financial_assertion_flags(text)==['UNSUPPORTED_UNCHANGED_BORROWING_COST']


@pytest.mark.parametrize('text',[
    'Нельзя утверждать, что прямого изменения стоимости заёмного финансирования не произошло.',
    'Если договор фиксирует ставку, стоимость кредита может оставаться прежней.',
    'Нет оснований утверждать, что стоимость кредитования не изменилась.',
    'Не подтверждено, что прямого изменения стоимости заёмного финансирования не произошло.',
])
def test_evaluation_financial_paraphrases_keep_qualifications(text):
    assert financial_assertion_flags(text)==[]


def compact_content():
    return {'relevance':'medium','summary':'Факт новости: ставка сохранена. Условие компании: закупка запасов до оплаты.',
        'risks':['Если нужны заёмные средства для запасов, следует уточнить их условия [Источник 1].'],
        'opportunities':[],
        'recommendations':['Проверить условия договоров и сроки оплаты.']}


def test_compact_checks_are_hints_and_do_not_change_required_schema():
    expected={'relevance','summary','risks','opportunities','recommendations'}
    assert set(AnalysisContent.model_fields)==expected
    assert set(AnalysisContent.model_json_schema()['required'])==expected
    content=AnalysisContent.model_validate(compact_content())
    assert output_checks(content)['violations']==[]
    assert 'JSON_OVER_1400_CHARACTERS' in output_checks(content,' '*1500+content.model_dump_json())['violations']
    content.summary='x'*241
    content.risks=['x'*141]*3
    report=output_checks(content)
    assert {'SUMMARY_OVER_240_CHARACTERS','RISKS_TOO_MANY_ITEMS','RISKS_ITEM_OVER_140_CHARACTERS'}<=set(report['violations'])
    assert report['human_review_required']
    checks=technical_checks(json.dumps(content.model_dump()),[{'id':1}],
        {**comparison.comparison_cases()[0],'evaluation_prompt_variant':VARIANT},'stop')
    assert checks['schema_valid'] and checks['compact_output']['violations']
    assert checks['factual_accuracy']=='NOT_ASSESSED'


def test_compact_prompt_changes_only_opt_in_instructions():
    base,base_plan=comparison.comparison_plan()
    compact,plan=comparison.comparison_plan(SimpleNamespace(compact=True))
    assert base_plan['prompt_variant']=='comparison-baseline-v1'
    assert plan['prompt_variant']==VARIANT and plan['limits']['max_output_tokens']==1000
    assert compact[0][1]['evidence']==compact[1][1]['evidence']==base[0][1]['evidence']
    for (a,old),(b,new) in zip(base,compact):
        assert a['company']==b['company'] and a['news']==b['news']
        assert old['messages'][0]==new['messages'][0]
        assert RULES not in old['messages'][1]['content'] and RULES in new['messages'][1]['content']
        assert new['messages'][1]['content'].replace(RULES,'')==old['messages'][1]['content']
    comparison.validate_fixed_pair(compact,plan)
    tampered=copy.deepcopy(compact)
    tampered[0][1]['messages'][1]['content']+='unexpected instructions'
    with pytest.raises(ValueError,match='COMPARISON_FIXTURE_MISMATCH'):comparison.validate_fixed_pair(tampered,plan)


def test_compact_pair_fake_sdk_persists_variant_and_checks(tmp_path):
    calls=[]
    async def create(**kwargs):
        calls.append(kwargs)
        assert RULES in kwargs['messages'][1]['content']
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(compact_content(),ensure_ascii=False)),finish_reason='stop')])
    sdk=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(side_effect=create))))
    async def complete(messages,*,max_tokens,timeout):
        response=await sdk.chat.completions.create(model='fake-no-llm',messages=messages,max_tokens=max_tokens)
        return {'raw':response.choices[0].message.content,'finish_reason':'stop','model':'fake-no-llm','usage':None}
    args=comparison.arguments(['--compact'])
    assert asyncio.run(comparison.execute(args,complete=complete,root=tmp_path))==0
    assert len(calls)==2
    folder=next(tmp_path.iterdir())
    manifest=json.loads((folder/'manifest.json').read_text())
    assert manifest['metadata']['prompt_variant']==VARIANT
    for case in comparison.comparison_cases():
        record=json.loads((folder/(case['id']+'.json')).read_text(encoding='utf-8'))
        assert record['checks']['compact_output']['violations']==[]
        assert set(json.loads(record['response']['raw']))==set(AnalysisContent.model_fields)


@pytest.mark.parametrize('reasoning',[None,0,123,-1,True])
def test_reasoning_accounting_is_optional_never_inferred_or_saved_as_text(reasoning):
    message=SimpleNamespace(content=json.dumps(compact_content()),reasoning_content='HIDDEN-REASONING-MUST-NOT-BE-PERSISTED')
    usage=SimpleNamespace(prompt_tokens=100,completion_tokens=200,total_tokens=300)
    if reasoning is not None:usage.completion_tokens_details=SimpleNamespace(reasoning_tokens=reasoning)
    response=SimpleNamespace(choices=[SimpleNamespace(message=message,finish_reason='stop')],usage=usage,model='fake')
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=response))))
    client.with_options=lambda **kwargs:client
    result=asyncio.run(complete_with_client(client,{'LLM_MODEL':'fake'},[],max_tokens=1000,timeout=60))
    reported=isinstance(reasoning,int) and not isinstance(reasoning,bool) and reasoning>=0
    assert result['token_accounting']['reasoning_tokens_reported']==reported
    assert result['token_accounting']['reasoning_tokens']==(reasoning if reported else None)
    assert result['token_accounting']['reasoning_content_present'] is True
    assert 'HIDDEN-REASONING' not in json.dumps(result)
    assert result['usage']['completion_tokens']==200


def test_missing_reasoning_content_is_unknown_not_false_evidence():
    response=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{}'),finish_reason='length')],
        usage=SimpleNamespace(prompt_tokens=10,completion_tokens=1000,total_tokens=1010),model='fake')
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=response))))
    client.with_options=lambda **kwargs:client
    result=asyncio.run(complete_with_client(client,{'LLM_MODEL':'fake'},[],max_tokens=1000,timeout=60))
    assert result['token_accounting']['reasoning_tokens'] is None
    assert result['token_accounting']['reasoning_content_present'] is None
