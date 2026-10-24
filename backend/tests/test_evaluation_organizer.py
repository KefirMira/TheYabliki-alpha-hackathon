import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from evaluation import __main__ as cli
from evaluation.inputs import synthetic_chunks
from evaluation.runner import fake_complete, make_plan, provider_budget_exceeded, run
from evaluation.scenarios import scenarios


def flags(*extra, plan=True):
    return ['--real','--organizer-gateway','--synthetic-rag','--scenario','macro-rate',
            '--allow-provider-host','changellenge.up.railway.app',
            *(['--plan'] if plan else ['--acknowledge-unknown-cost','--allow-rag-transfer']),*extra]


def quota_plan():
    limits=dict(max_requests=1,max_input_tokens=16000,max_output_tokens=1000,
        request_seconds=60,total_seconds=60,billing_mode='organizer_rub_quota',
        input_rate=None,output_rate=None,budget_usd=None)
    return make_plan(scenarios()[:1],synthetic_chunks(),limits)


@pytest.mark.parametrize('extra',[
    ['--max-requests','2'],['--max-output-tokens','1001'],['--max-input-tokens','16001'],
    ['--request-seconds','61'],['--total-seconds','61'],['--input-usd-per-million','1'],
    ['--output-usd-per-million','1'],['--budget-usd','1'],['--rag-dir','private'],
    ['--scenario','gold-producer'],
])
def test_organizer_rejects_relaxed_limits_and_invented_prices(extra):
    with pytest.raises(SystemExit):cli.arguments(flags(*extra))


@pytest.mark.parametrize('missing',['--real','--synthetic-rag','--acknowledge-unknown-cost','--allow-rag-transfer'])
def test_organizer_requires_explicit_execution_permissions(missing):
    args=flags(plan=False)
    args.remove(missing)
    with pytest.raises(SystemExit):cli.arguments(args)


def test_organizer_plan_no_sdk_corpus_or_database(monkeypatch,capsys):
    monkeypatch.setattr(cli,'configuration',lambda args:{'LLM_API_KEY':'synthetic-secret'})
    monkeypatch.setattr(cli,'real_client',lambda config:pytest.fail('Plan constructed SDK'))
    monkeypatch.setattr(cli,'load_chunks',lambda *args:pytest.fail('Loaded private corpus'))
    assert cli.main(flags())==0
    report=json.loads(capsys.readouterr().out)
    assert report['mode']=='real'
    plan=report['plan']
    assert plan['planned_requests']==1 and plan['scenario_count']==1
    assert plan['limits']['total_seconds']==60
    assert plan['estimated_upper_usd'] is None
    assert plan['limits']['budget_usd'] is None
    assert 'monetary limit' in plan['pricing_note']
    assert set(plan['input_token_planning_bounds'])=={'macro-rate'}


@pytest.mark.parametrize('base',sorted(cli.ORGANIZER_URLS))
def test_organizer_configuration_allows_only_explicit_gateway(monkeypatch,base):
    import dotenv
    monkeypatch.setattr(dotenv,'dotenv_values',lambda path:{})
    monkeypatch.setenv('LLM_BASE_URL',base)
    monkeypatch.setenv('LLM_MODEL',cli.ORGANIZER_MODEL)
    monkeypatch.setenv('LLM_API_KEY','synthetic-secret')
    args=cli.arguments(flags())
    from urllib.parse import urlsplit
    args.allow_provider_host=urlsplit(base).hostname
    assert cli.configuration(args)['LLM_BASE_URL']==base
    monkeypatch.setenv('LLM_BASE_URL',base+'/unexpected')
    with pytest.raises(ValueError,match='ORGANIZER_CONFIGURATION'):cli.configuration(args)
    monkeypatch.setenv('LLM_BASE_URL',base)
    monkeypatch.setenv('LLM_MODEL','different-model')
    with pytest.raises(ValueError,match='ORGANIZER_CONFIGURATION'):cli.configuration(args)
    monkeypatch.setenv('LLM_MODEL',cli.ORGANIZER_MODEL)
    monkeypatch.setenv('AI_MODE','demo')
    with pytest.raises(ValueError,match='AI_DISABLED_IN_DEMO'):cli.configuration(args)


def test_organizer_usage_without_false_zero_cost(tmp_path):
    prepared,plan=quota_plan()
    calls=[]
    async def complete(*args,**kwargs):
        calls.append(kwargs)
        result=await fake_complete(*args,**kwargs)
        result['usage']={'prompt_tokens':500,'completion_tokens':100,'total_tokens':600}
        return result
    folder=asyncio.run(run(prepared,plan,complete,real=True,root=tmp_path))
    summary=json.loads((folder/'summary.json').read_text())
    assert len(calls)==1 and calls[0]['max_tokens']==1000 and calls[0]['timeout']<=60
    assert summary['attempted']==1 and not summary['stopped']
    assert summary['estimated_actual_usd'] is summary['known_usage_estimated_usd'] is None
    assert summary['billing_complete'] is False
    record=json.loads((folder/'macro-rate.json').read_text(encoding='utf-8'))
    assert record['response']['usage']['total_tokens']==600
    assert record['cost_status']=='UNKNOWN_ORGANIZER_QUOTA'
    assert record['request']['evidence'][0]['document']=='synthetic-evaluation.txt'


@pytest.mark.parametrize('failure',['budget','timeout','network'])
def test_organizer_cli_one_attempt_no_fallback_no_secret_logs(monkeypatch,tmp_path,capsys,failure):
    class BudgetError(Exception):
        status_code=429
        body={'error':{'message':'Budget has been exceeded: synthetic-secret'}}
    create=AsyncMock(side_effect={'budget':BudgetError('synthetic-secret'),
        'timeout':TimeoutError('synthetic-secret'),'network':OSError('synthetic-secret')}[failure])
    closed=AsyncMock()
    options=[]
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)),close=closed)
    def with_options(**kwargs):
        options.append(kwargs)
        return client
    client.with_options=with_options
    clients=[]
    def factory(config):
        clients.append(config['LLM_BASE_URL'])
        return client
    monkeypatch.setattr(cli,'configuration',lambda args:{'LLM_API_KEY':'synthetic-secret',
        'LLM_BASE_URL':'https://changellenge.up.railway.app/v1','LLM_MODEL':cli.ORGANIZER_MODEL})
    monkeypatch.setattr(cli,'real_client',factory)
    async def local_run(*args,**kwargs):return await run(*args,root=tmp_path,**kwargs)
    monkeypatch.setattr(cli,'run',local_run)
    assert cli.main(flags(plan=False))==1
    assert clients==['https://changellenge.up.railway.app/v1']
    create.assert_awaited_once()
    closed.assert_awaited_once()
    assert options[0]['max_retries']==0 and options[0]['timeout']<=60
    assert create.await_args.kwargs['max_tokens']==1000
    output=capsys.readouterr().out
    folder=next(tmp_path.iterdir())
    assert 'synthetic-secret' not in output+''.join(p.read_text(encoding='utf-8') for p in folder.iterdir())
    report=json.loads((folder/'summary.json').read_text())
    record=json.loads((folder/'macro-rate.json').read_text(encoding='utf-8'))
    assert report['attempted']==1 and report['stopped'] and (folder/'macro-rate.intent.json').exists()
    if failure=='budget':
        assert record['status']=='BUDGET_EXCEEDED_NO_RETRY'
        assert record['error_code']=='PROVIDER_BUDGET_EXCEEDED'
        assert 'PROVIDER_BUDGET_EXCEEDED' in output
    else:assert record['status']=='ERROR_NO_RETRY'


def test_organizer_runner_rejects_unsafe_plan_before_writes(tmp_path):
    prepared,plan=quota_plan()
    plan['limits']['max_requests']=2
    with pytest.raises(ValueError,match='INVALID_ORGANIZER_LIMITS'):
        asyncio.run(run(prepared,plan,AsyncMock(),real=True,root=tmp_path))
    assert not list(tmp_path.iterdir())


def test_budget_classification_is_narrow():
    assert not provider_budget_exceeded(TimeoutError('Budget has been exceeded'))
    assert not provider_budget_exceeded(SimpleNamespace(status_code=429,body={'message':'Rate limit'}))
