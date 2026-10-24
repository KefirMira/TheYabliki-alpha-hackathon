"""No network/SDK: expanded output budget belongs only to the fixed single test."""
import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from evaluation import __main__ as cli, comparison
from evaluation.compact import RULES, VARIANT
from evaluation.inputs import synthetic_chunks
from evaluation.runner import make_plan, run, validate_real_plan
from evaluation.scenarios import scenarios


def flags(*extra):
    return ['--real', '--organizer-gateway', '--synthetic-rag', '--scenario', 'macro-rate',
            '--allow-provider-host', 'changellenge.up.railway.app', *extra]


def single_plan(compact=False):
    cases = scenarios()[:1]
    if compact:
        cases = [{**case, 'evaluation_prompt_variant': VARIANT} for case in cases]
    limits = dict(max_requests=1, max_input_tokens=8000, max_output_tokens=2000,
                  request_seconds=60, total_seconds=60, billing_mode='organizer_rub_quota',
                  input_rate=None, output_rate=None, budget_usd=None)
    prepared, plan = make_plan(cases, synthetic_chunks(), limits,
                               question_suffix=RULES if compact else '')
    plan['prompt_variant'] = VARIANT if compact else 'baseline'
    return prepared, plan


def test_single_defaults_and_explicit_expansion():
    assert cli.arguments(flags('--plan')).max_output_tokens == 1000
    assert not cli.arguments(flags('--plan')).compact
    assert cli.arguments(flags('--plan', '--compact', '--max-output-tokens', '2000')).max_output_tokens == 2000
    assert comparison.arguments([]).max_output_tokens == 1000


@pytest.mark.parametrize('extra', [
    ['--max-output-tokens', '2001'], ['--max-output-tokens', '3000'],
    ['--max-requests', '2'], ['--scenario', 'gold-producer'],
    ['--rag-dir', 'private'], ['--allow-provider-host', 'api.alfahack-gateway26.ru'],
])
def test_expanded_cli_rejects_unapproved_scope(extra):
    with pytest.raises(SystemExit):
        cli.arguments(flags('--plan', '--max-output-tokens', '2000', *extra))


def test_expanded_requires_synthetic_rag():
    args = flags('--plan', '--max-output-tokens', '2000')
    args.remove('--synthetic-rag')
    with pytest.raises(SystemExit):
        cli.arguments(args)


def test_expanded_configuration_rejects_backup_or_different_model(monkeypatch):
    import dotenv
    monkeypatch.setattr(dotenv, 'dotenv_values', lambda path: {})
    monkeypatch.setenv('LLM_API_KEY', 'synthetic-secret')
    monkeypatch.setenv('LLM_BASE_URL', 'https://api.alfahack-gateway26.ru/v1')
    monkeypatch.setenv('LLM_MODEL', cli.ORGANIZER_MODEL)
    args = cli.arguments(flags('--plan', '--max-output-tokens', '2000'))
    args.allow_provider_host = 'api.alfahack-gateway26.ru'
    with pytest.raises(ValueError, match='ORGANIZER_CONFIGURATION'):
        cli.configuration(args)
    args.allow_provider_host = 'changellenge.up.railway.app'
    monkeypatch.setenv('LLM_BASE_URL', 'https://changellenge.up.railway.app/v1')
    assert cli.configuration(args)['LLM_MODEL'] == cli.ORGANIZER_MODEL
    monkeypatch.setenv('LLM_MODEL', 'other')
    with pytest.raises(ValueError, match='ORGANIZER_CONFIGURATION'):
        cli.configuration(args)


@pytest.mark.parametrize('tokens', [1001, 2000, 2001])
def test_pair_stays_capped_in_cli_and_runner(tokens):
    with pytest.raises(SystemExit):
        comparison.arguments(['--max-output-tokens', str(tokens)])
    _, plan = comparison.comparison_plan()
    plan['limits']['max_output_tokens'] = tokens
    with pytest.raises(ValueError, match='INVALID_ORGANIZER_LIMITS'):
        validate_real_plan(plan)


def test_runner_rejects_2001_and_mutated_synthetic_fixture_before_intent(tmp_path):
    prepared, plan = single_plan()
    invalid = copy.deepcopy(plan)
    invalid['limits']['max_output_tokens'] = 2001
    complete = AsyncMock()
    with pytest.raises(ValueError, match='INVALID_ORGANIZER_LIMITS'):
        asyncio.run(run(prepared, invalid, complete, real=True, root=tmp_path))
    prepared[0][1]['messages'][1]['content'] += 'UNAPPROVED INPUT'
    with pytest.raises(ValueError, match='ORGANIZER_FIXTURE_MISMATCH'):
        asyncio.run(run(prepared, plan, complete, real=True, root=tmp_path))
    complete.assert_not_called()
    assert not list(tmp_path.iterdir())


def test_compact_single_plan_has_no_sdk_or_private_corpus(monkeypatch, capsys):
    monkeypatch.setattr(cli, 'configuration', lambda args: {})
    monkeypatch.setattr(cli, 'real_client', lambda *a: pytest.fail('SDK in plan'))
    monkeypatch.setattr(cli, 'load_chunks', lambda *a: pytest.fail('Private corpus'))
    assert cli.main(flags('--plan', '--compact', '--max-output-tokens', '2000')) == 0
    plan = json.loads(capsys.readouterr().out)['plan']
    assert plan['planned_requests'] == plan['scenario_count'] == 1
    assert plan['prompt_variant'] == VARIANT
    assert plan['limits']['max_output_tokens'] == 2000
    assert plan['estimated_upper_usd'] is None


@pytest.mark.parametrize('outcome', ['valid', 'empty', 'invalid', 'length', 'timeout'])
def test_single_fake_sdk_exactly_once_preserves_accounting_and_failure_exit(monkeypatch, tmp_path, outcome):
    raw = json.dumps(dict(relevance='medium', summary='Условный риск [Источник 1].',
                          risks=[], opportunities=[], recommendations=[]), ensure_ascii=False)
    if outcome == 'empty': raw = ''
    if outcome == 'invalid': raw = '{'
    response = SimpleNamespace(model='fake',
        choices=[SimpleNamespace(message=SimpleNamespace(content=raw),
                                 finish_reason='length' if outcome == 'length' else 'stop')],
        usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=1500, total_tokens=2500,
                              completion_tokens_details=SimpleNamespace(reasoning_tokens=1000)))
    create = AsyncMock(return_value=response)
    if outcome == 'timeout': create.side_effect = TimeoutError()
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)), close=AsyncMock())
    options = []
    def with_options(**kwargs):
        options.append(kwargs)
        return client
    client.with_options = with_options
    monkeypatch.setattr(cli, 'configuration', lambda args: {'LLM_MODEL': cli.ORGANIZER_MODEL})
    factory = Mock(side_effect=lambda config: client)
    monkeypatch.setattr(cli, 'real_client', factory)
    async def local_run(*args, **kwargs):
        return await run(*args, root=tmp_path, **kwargs)
    monkeypatch.setattr(cli, 'run', local_run)
    code = cli.main(flags('--compact', '--max-output-tokens', '2000',
                          '--allow-rag-transfer', '--acknowledge-unknown-cost'))
    assert code == (0 if outcome == 'valid' else 1)
    create.assert_awaited_once()
    factory.assert_called_once()
    client.close.assert_awaited_once()
    assert options[0]['max_retries'] == 0 and options[0]['timeout'] <= 60
    assert set(create.await_args.kwargs) == {'model', 'messages', 'max_tokens'}
    assert create.await_args.kwargs['max_tokens'] == 2000
    assert RULES in create.await_args.kwargs['messages'][1]['content']
    folder = next(tmp_path.iterdir())
    record = json.loads((folder/'macro-rate.json').read_text(encoding='utf-8'))
    assert record['request']['evidence'][0]['document'] == 'synthetic-evaluation.txt'
    if outcome != 'timeout':
        assert record['response']['raw'] == raw  # Never truncate or repair locally.
        assert record['response']['token_accounting']['reasoning_tokens'] == 1000
        assert record['response']['usage']['completion_tokens'] == 1500
    assert json.loads((folder/'summary.json').read_text())['attempted'] == 1
