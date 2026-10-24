import asyncio
import copy
import csv
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from evaluation import comparison
from evaluation.runner import validate_real_plan


def flags(*extra,plan=False):
    return ['--real','--organizer-gateway','--synthetic-rag',
        '--allow-provider-host','changellenge.up.railway.app',
        *(['--plan'] if plan else ['--allow-rag-transfer','--acknowledge-unknown-cost']),*extra]


@pytest.mark.parametrize('extra',[
    ['--max-requests','1'],['--max-requests','3'],['--max-output-tokens','1001'],
    ['--max-input-tokens','8001'],['--request-seconds','61'],['--total-seconds','121'],
    ['--request-seconds','nan'],['--total-seconds','inf'],['--rag-dir','private'],
    ['--scenario','other'],['--budget-usd','1'],
])
def test_real_comparison_rejects_unsafe_flags(extra):
    with pytest.raises(SystemExit):comparison.arguments(flags(*extra))


@pytest.mark.parametrize('missing',['--organizer-gateway','--synthetic-rag',
                                  '--allow-rag-transfer','--acknowledge-unknown-cost'])
def test_real_comparison_requires_explicit_flags(missing):
    args=flags()
    args.remove(missing)
    with pytest.raises(SystemExit):comparison.arguments(args)


def test_real_comparison_plan_never_constructs_sdk(monkeypatch,tmp_path,capsys):
    monkeypatch.setattr(comparison,'configuration',lambda args:{'LLM_API_KEY':'synthetic-secret'})
    monkeypatch.setattr(comparison,'real_client',lambda config:pytest.fail('SDK in plan'))
    assert asyncio.run(comparison.execute(comparison.arguments(flags(plan=True)),root=tmp_path))==0
    assert not list(tmp_path.iterdir())
    output=capsys.readouterr().out
    assert 'synthetic-secret' not in output
    assert json.loads(output)['plan']['planned_requests']==2


def fake_response(index=0):
    raw=json.dumps({'relevance':'medium','summary':
        'Если нужно финансировать запасы топлива, уточнить условия [Источник 1].' if index==0
        else 'Проверить оплату этапов проекта и затраты на персонал [Источник 1].',
        'risks':[],'opportunities':[],'recommendations':['Долг и ставки неизвестны.']},ensure_ascii=False)
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=raw),finish_reason='stop')],
        model='deepseek/deepseek-v4.1-flash',usage=SimpleNamespace(prompt_tokens=850,completion_tokens=250,total_tokens=1100))


def install_fake_sdk(monkeypatch,handler):
    options=[]
    client=SimpleNamespace(close=AsyncMock())
    create=AsyncMock(side_effect=handler)
    client.chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    def with_options(**kwargs):
        options.append(kwargs)
        return client
    client.with_options=with_options
    hosts=[]
    def factory(config):
        hosts.append(config['LLM_BASE_URL'])
        return client
    monkeypatch.setattr(comparison,'configuration',lambda args:{'LLM_API_KEY':'synthetic-secret',
        'LLM_BASE_URL':'https://changellenge.up.railway.app/v1','LLM_MODEL':'deepseek/deepseek-v4.1-flash'})
    monkeypatch.setattr(comparison,'real_client',factory)
    return client,create,options,hosts


def test_real_comparison_success_is_sequential_two_calls_and_saves_usage(monkeypatch,tmp_path):
    active=0
    seen=[]
    async def create(**kwargs):
        nonlocal active
        active+=1
        assert active==1
        index=len(seen)
        seen.append(kwargs)
        await asyncio.sleep(.001)
        active-=1
        return fake_response(index)
    client,create,options,hosts=install_fake_sdk(monkeypatch,create)
    args=comparison.arguments(flags())
    assert asyncio.run(comparison.execute(args,root=tmp_path))==0
    assert create.await_count==2
    client.close.assert_awaited_once()
    assert hosts==['https://changellenge.up.railway.app/v1']
    assert len(options)==2 and all(o['max_retries']==0 and o['timeout']<=60 for o in options)
    assert all(s['max_tokens']==1000 for s in seen)
    assert 'SYNTH-COMPARE-fuel' in seen[0]['messages'][1]['content']
    assert 'SYNTH-COMPARE-software' in seen[1]['messages'][1]['content']
    folder=next(tmp_path.iterdir())
    report=json.loads((folder/'comparison.json').read_text(encoding='utf-8'))
    assert report['mode']=='real' and report['quality_score'] is None
    assert all(p['usage']['total_tokens']==1100 for p in report['profiles'].values())
    records=[json.loads((folder/(c['id']+'.json')).read_text(encoding='utf-8')) for c in comparison.comparison_cases()]
    assert records[0]['request']['evidence']==records[1]['request']['evidence']
    assert all(r['scenario']['company']['revenue'] is None and r['mode']=='real' for r in records)
    assert len(list(folder.glob('*.intent.json')))==2
    with (folder/'comparison-responses.tsv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f,delimiter='\t'))
    assert len(rows)==2 and all(row['mode']=='real' for row in rows)
    assert 'топлива' in rows[0]['summary'] and 'персонал' in rows[1]['summary']
    summary=json.loads((folder/'summary.json').read_text())
    assert summary['attempted']==2 and summary['estimated_actual_usd'] is None and not summary['billing_complete']


@pytest.mark.parametrize('failure',['timeout','network','budget','empty','malformed','truncated',
                                  'missing_usage','invalid_citation','too_many_tokens','no_choices'])
def test_real_comparison_stops_after_first_unsafe_result(monkeypatch,tmp_path,capsys,failure):
    class BudgetError(Exception):
        status_code=429
        body={'error':{'message':'Budget has been exceeded: synthetic-secret'}}
    async def handler(**kwargs):
        if failure=='timeout':raise TimeoutError('synthetic-secret')
        if failure=='network':raise OSError('synthetic-secret')
        if failure=='budget':raise BudgetError('synthetic-secret')
        response=fake_response()
        if failure=='empty':response.choices[0].message.content=''
        if failure=='malformed':response.choices[0].message.content='invalid-json'
        if failure=='truncated':response.choices[0].finish_reason='length'
        if failure=='missing_usage':response.usage=None
        if failure=='invalid_citation':response.choices[0].message.content=response.choices[0].message.content.replace('Источник 1','Источник 99')
        if failure=='too_many_tokens':response.usage.completion_tokens=1001
        if failure=='no_choices':response.choices=[]
        return response
    client,create,options,hosts=install_fake_sdk(monkeypatch,handler)
    assert asyncio.run(comparison.execute(comparison.arguments(flags()),root=tmp_path))==1
    create.assert_awaited_once()
    client.close.assert_awaited_once()
    assert hosts==['https://changellenge.up.railway.app/v1']
    folder=next(tmp_path.iterdir())
    summary=json.loads((folder/'summary.json').read_text())
    assert summary['attempted']==1 and summary['stopped']
    second=json.loads((folder/'comparison-rate-software.json').read_text(encoding='utf-8'))
    assert second['status']=='NOT_ATTEMPTED' and second['response'] is None
    assert not (folder/'comparison-rate-software.intent.json').exists()
    assert (folder/'comparison-review.tsv').exists() and (folder/'comparison-responses.tsv').exists()
    assert 'synthetic-secret' not in capsys.readouterr().out+''.join(p.read_text(encoding='utf-8') for p in folder.iterdir())
    if failure=='budget':assert summary['error_codes']=={'comparison-rate-fuel':'PROVIDER_BUDGET_EXCEEDED'}


def test_real_comparison_second_failure_preserves_first_without_third_call(monkeypatch,tmp_path):
    seen=[]
    async def create(**kwargs):
        seen.append(kwargs)
        if len(seen)==2:raise OSError('synthetic-secret')
        return fake_response()
    _,mock,_,_=install_fake_sdk(monkeypatch,create)
    assert asyncio.run(comparison.execute(comparison.arguments(flags()),root=tmp_path))==1
    assert mock.await_count==2
    folder=next(tmp_path.iterdir())
    first=json.loads((folder/'comparison-rate-fuel.json').read_text(encoding='utf-8'))
    assert first['status']=='RECEIVED' and first['response']['usage']['total_tokens']==1100
    assert len(list(folder.glob('*.intent.json')))==2


def test_real_comparison_wall_timeout_cancels_before_second(monkeypatch,tmp_path):
    async def slow(**kwargs):await asyncio.sleep(10)
    _,mock,_,_=install_fake_sdk(monkeypatch,slow)
    args=comparison.arguments(flags('--request-seconds','1'))
    assert asyncio.run(comparison.execute(args,root=tmp_path))==1
    mock.assert_awaited_once()
    summary=json.loads((next(tmp_path.iterdir())/'summary.json').read_text())
    assert summary['stopped'] and summary['attempted']==1


@pytest.mark.parametrize('mutation',['profile','news','evidence'])
def test_real_comparison_rejects_modified_fixed_inputs(monkeypatch,tmp_path,mutation):
    prepared,plan=copy.deepcopy(comparison.comparison_plan())
    if mutation=='profile':prepared[0][0]['company']['industry']='Unexpected private input'
    if mutation=='news':prepared[0][0]['news']='Unexpected private input'
    if mutation=='evidence':prepared[0][1]['evidence'][0]['text']='Unexpected private input'
    monkeypatch.setattr(comparison,'comparison_plan',lambda args:(prepared,plan))
    monkeypatch.setattr(comparison,'real_client',lambda config:pytest.fail('SDK for modified input'))
    with pytest.raises(ValueError,match='COMPARISON_FIXTURE_MISMATCH'):
        asyncio.run(comparison.execute(comparison.arguments(flags()),root=tmp_path))
    assert not list(tmp_path.iterdir())


def test_real_comparison_redacts_table_and_escapes_spreadsheet_formula(monkeypatch,tmp_path):
    async def handler(**kwargs):
        response=fake_response()
        raw=json.loads(response.choices[0].message.content)
        raw['summary']='=synthetic-secret'
        response.choices[0].message.content=json.dumps(raw)
        return response
    install_fake_sdk(monkeypatch,handler)
    assert asyncio.run(comparison.execute(comparison.arguments(flags()),root=tmp_path))==0
    folder=next(tmp_path.iterdir())
    assert 'synthetic-secret' not in ''.join(p.read_text(encoding='utf-8') for p in folder.iterdir())
    with (folder/'comparison-responses.tsv').open(encoding='utf-8',newline='') as file:
        rows=list(csv.DictReader(file,delimiter='\t'))
    assert all(row['summary'].startswith("'=") for row in rows)
