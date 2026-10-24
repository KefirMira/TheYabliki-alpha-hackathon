import asyncio
from decimal import Decimal
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from evaluation import __main__ as cli
from evaluation.inputs import synthetic_chunks
from evaluation.runner import estimate, fake_complete, make_plan, run, technical_checks, token_bound
from evaluation.scenarios import scenarios


def limits(**updates):
    return dict(max_requests=10, max_input_tokens=16000, max_output_tokens=1000,
                request_seconds=1, total_seconds=10, input_rate=Decimal('1'),
                output_rate=Decimal('2'), budget_usd=Decimal('1'), **updates)


def plan(cases=None):
    return make_plan(cases or scenarios()[:2], synthetic_chunks(), limits())


def test_fake_default_and_no_sdk_or_credentials(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, 'real_client', lambda *a: pytest.fail('SDK called in fake mode'))
    monkeypatch.setattr(cli, 'configuration', lambda a: {})
    import evaluation.runner as runner
    original = run
    async def local(*args, **kwargs):
        return await original(*args, root=tmp_path, **kwargs)
    monkeypatch.setattr(cli, 'run', local)
    assert cli.main(['--synthetic-rag']) == 0
    folder = next(tmp_path.iterdir())
    summary = json.loads((folder / 'summary.json').read_text())
    assert summary['attempted'] == 8 and summary['estimated_actual_usd'] == '0'
    assert (folder / 'manual-review.tsv').exists()
    result = json.loads((folder / 'macro-rate.json').read_text(encoding='utf-8'))
    assert result['checks']['schema_valid'] is True
    assert result['checks']['factual_accuracy'] == 'NOT_ASSESSED'
    assert result['response']['usage'] is None


@pytest.mark.parametrize('argv', [
    ['--real'], ['--max-requests', '11'], ['--max-output-tokens', '4001'],
    ['--total-seconds', '0'], ['--request-seconds', 'nan'], ['--budget-usd', 'NaN'],
    ['--input-usd-per-million', '-1'], ['--max-input-tokens', '64001'],
])
def test_invalid_flags_fail_before_any_call(argv):
    with pytest.raises(SystemExit):
        cli.arguments(argv)


def test_precise_plan_and_input_rejection():
    assert estimate(1000, 500, Decimal('1'), Decimal('2')) == Decimal('.002')
    prepared, summary = plan()
    assert summary['planned_requests'] == 2
    assert token_bound(prepared[0][1]['messages']) >= len(prepared[0][1]['messages'][1]['content'])
    config = limits()
    config['max_input_tokens'] = 1
    with pytest.raises(ValueError, match='INPUT_LIMIT'):
        make_plan(scenarios()[:1], synthetic_chunks(), config)


@pytest.mark.parametrize('restriction', ['budget_usd', 'max_requests'])
def test_budget_and_request_limit_prevent_call(tmp_path, restriction):
    prepared, summary = plan()
    summary['limits'][restriction] = Decimal('.000001') if restriction == 'budget_usd' else 1
    complete = AsyncMock()
    with pytest.raises(ValueError, match='REQUEST_OR_BUDGET'):
        asyncio.run(run(prepared, summary, complete, real=True, root=tmp_path))
    complete.assert_not_called()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('failure', ['timeout', 'network', 'missing_usage', 'too_many_tokens'])
def test_real_path_simulated_no_retries_and_stops(tmp_path, failure):
    prepared, summary = plan()
    calls = []
    async def complete(messages, **options):
        calls.append(options)
        if failure == 'timeout':
            raise TimeoutError('Secret request headers must not be saved')
        if failure == 'network':
            raise OSError('Secret request body')
        response = await fake_complete(messages, **options)
        if failure == 'too_many_tokens':
            response['usage'] = {'prompt_tokens': 1, 'completion_tokens': 1001}
        return response
    folder = asyncio.run(run(prepared, summary, complete, real=True, root=tmp_path))
    assert len(calls) == 1
    results = [json.loads((folder / f"{c['id']}.json").read_text(encoding='utf-8')) for c, _ in prepared]
    assert results[1]['status'] == 'NOT_ATTEMPTED'
    assert (folder / (prepared[0][0]['id'] + '.intent.json')).exists()
    report = json.loads((folder / 'summary.json').read_text())
    if failure in {'timeout', 'network', 'missing_usage'}:
        assert report['estimated_actual_usd'] is None and not report['billing_complete']
    assert 'Secret request' not in ''.join(p.read_text(encoding='utf-8') for p in folder.iterdir())


def test_real_usage_and_key_redaction(tmp_path):
    prepared, summary = plan(scenarios()[:1])
    async def complete(*args, **kwargs):
        response = await fake_complete(*args, **kwargs)
        response['raw'] = response['raw'].replace('Синтетический', 'synthetic-secret-value')
        response['usage'] = {'prompt_tokens': 100, 'completion_tokens': 100, 'total_tokens': 200}
        return response
    folder = asyncio.run(run(prepared, summary, complete, real=True, secret='synthetic-secret-value', root=tmp_path))
    assert 'synthetic-secret-value' not in ''.join(p.read_text(encoding='utf-8') for p in folder.iterdir())
    assert json.loads((folder / 'summary.json').read_text())['estimated_actual_usd'] == '0.0003'


def test_no_context_never_calls_ai(tmp_path):
    prepared, summary = make_plan(scenarios()[:1], [], limits())
    complete = AsyncMock()
    folder = asyncio.run(run(prepared, summary, complete, real=True, root=tmp_path))
    complete.assert_not_called()
    assert json.loads((folder / 'summary.json').read_text())['attempted'] == 0


def test_technical_checks_are_not_truth_or_citation_verification():
    case = scenarios()[0]
    raw = json.dumps({'relevance': 'high', 'summary': 'Необоснованный вывод [Источник 99]',
                      'risks': [], 'opportunities': [], 'recommendations': []})
    checks = technical_checks(raw, [{'id': 1}], case, 'length')
    assert checks['schema_valid'] and checks['truncated']
    assert checks['citation_ids_valid'] is False
    assert checks['human_review_required'] and checks['factual_accuracy'] == 'NOT_ASSESSED'
    assert not technical_checks('bad JSON', [], case, 'stop')['schema_valid']


def real_args():
    return cli.arguments(['--real', '--plan', '--synthetic-rag', '--scenario', 'macro-rate',
        '--input-usd-per-million', '1', '--output-usd-per-million', '2', '--budget-usd', '.05',
        '--allow-provider-host', 'synthetic.example.invalid'])


@pytest.mark.parametrize('url', ['http://synthetic.example.invalid', 'https://other.example.invalid',
    'https://synthetic.example.invalid/?secret=value', 'https://user:pass@synthetic.example.invalid'])
def test_provider_endpoint_is_explicit_and_no_credentials_in_url(monkeypatch, url):
    import dotenv
    monkeypatch.setattr(dotenv, 'dotenv_values', lambda path: {})
    monkeypatch.setenv('LLM_BASE_URL', url)
    monkeypatch.setenv('LLM_MODEL', 'synthetic')
    monkeypatch.setenv('LLM_API_KEY', 'synthetic-key')
    with pytest.raises(ValueError, match='PROVIDER_NOT'):
        cli.configuration(real_args())


def test_real_plan_never_constructs_client(monkeypatch):
    monkeypatch.setattr(cli, 'configuration', lambda args: {'LLM_API_KEY': 'synthetic-key'})
    monkeypatch.setattr(cli, 'real_client', lambda config: pytest.fail('Real SDK constructed by plan'))
    assert asyncio.run(cli.execute(real_args())) == 0


def test_demo_blocks_real_even_with_explicit_flags(monkeypatch):
    import dotenv
    monkeypatch.setattr(dotenv, 'dotenv_values', lambda path: {})
    for k, v in {'LLM_BASE_URL': 'https://synthetic.example.invalid', 'LLM_MODEL': 'synthetic',
                 'LLM_API_KEY': 'synthetic-key', 'AI_MODE': 'demo'}.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(ValueError, match='AI_DISABLED'):
        cli.configuration(real_args())


def test_sdk_is_configured_with_no_retries_or_redirects(monkeypatch):
    import sys
    captured = {}
    def transport(**kwargs):
        captured['transport'] = kwargs
        return object()
    def client(**kwargs):
        captured['client'] = kwargs
        return object()
    monkeypatch.setitem(sys.modules, 'openai', SimpleNamespace(AsyncOpenAI=client, DefaultAsyncHttpxClient=transport))
    cli.real_client({'LLM_API_KEY': 'synthetic', 'LLM_BASE_URL': 'https://synthetic.example.invalid', 'LLM_MODEL': 'synthetic'})
    assert captured['client']['max_retries'] == 0
    assert captured['transport'] == {'follow_redirects': False, 'trust_env': False}


def test_wall_timeout_cancels_one_attempt_without_retry(tmp_path):
    prepared, summary = plan()
    summary['limits']['request_seconds'] = .01
    complete = AsyncMock(side_effect=lambda *a, **kw: None)
    calls = []
    async def slow(*args, **kwargs):
        calls.append(True)
        await asyncio.sleep(10)
    folder = asyncio.run(run(prepared, summary, slow, real=True, root=tmp_path))
    assert len(calls) == 1
    report = json.loads((folder / 'summary.json').read_text())
    assert report['stopped'] and report['estimated_actual_usd'] is None


def test_missing_corpus_is_explicit(tmp_path):
    args = cli.arguments(['--rag-dir', str(tmp_path)])
    with pytest.raises(ValueError, match='MISSING_OR_INVALID'):
        cli.load_corpus(args, {})


def test_output_is_ignored_by_git():
    import subprocess
    root = Path(__file__).resolve().parents[2]
    for name in ('backend/evaluation-results/example/result.json',
                 'backend/evaluation-results/example/manual-review.tsv'):
        result = subprocess.run(['git', 'check-ignore', '--quiet', name], cwd=root)
        assert result.returncode == 0
