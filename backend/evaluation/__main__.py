"""python -m evaluation. Fake by default; no SDK/env secret loading without --real."""
import argparse
import asyncio
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from evaluation.inputs import synthetic_chunks
from evaluation.runner import make_plan, run, validate_real_plan
from evaluation.scenarios import scenarios
from services.chunk_service import load_chunks

BASE = Path(__file__).resolve().parents[1]
ORGANIZER_URLS = {'https://changellenge.up.railway.app/v1', 'https://api.alfahack-gateway26.ru/v1'}
ORGANIZER_MODEL = 'deepseek/deepseek-v4.1-flash'


def money(value):
    try:
        result = Decimal(value)
        if not result.is_finite() or result <= 0:
            raise ValueError
        return result
    except (InvalidOperation, ValueError):
        raise argparse.ArgumentTypeError('Use a finite positive decimal') from None


def arguments(argv=None):
    parser = argparse.ArgumentParser(description='Offline-first DeepSeek/RAG evaluation; real mode costs money')
    parser.add_argument('--real', action='store_true')
    parser.add_argument('--organizer-gateway', action='store_true', help='Single synthetic test against the organizer RUB quota; no USD estimate')
    parser.add_argument('--acknowledge-unknown-cost', action='store_true', help='Acknowledge unknown per-request cost and shared quota')
    parser.add_argument('--plan', action='store_true', help='Local preflight only, never call SDK')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--scenario', action='append', choices=[c['id'] for c in scenarios()])
    parser.add_argument('--synthetic-rag', action='store_true')
    parser.add_argument('--rag-dir', type=Path)
    parser.add_argument('--max-requests', type=int, choices=range(1, 11), default=1)
    parser.add_argument('--max-input-tokens', type=int, default=16000)
    parser.add_argument('--max-output-tokens', type=int, default=1000)
    parser.add_argument('--request-seconds', type=float, default=60)
    parser.add_argument('--total-seconds', type=float)
    parser.add_argument('--input-usd-per-million', type=money)
    parser.add_argument('--output-usd-per-million', type=money)
    parser.add_argument('--budget-usd', type=money)
    parser.add_argument('--allow-provider-host')
    parser.add_argument('--allow-rag-transfer', action='store_true', help='Confirm permission to send selected corpus excerpts')
    args = parser.parse_args(argv)
    if args.total_seconds is None:
        args.total_seconds = 60 if args.organizer_gateway else 180
    if not (1 <= args.max_input_tokens <= 64000 and 1 <= args.max_output_tokens <= 4000
            and 1 <= args.request_seconds <= 120 and 1 <= args.total_seconds <= 900):
        parser.error('Input/output/time limit outside safe range')
    prices = (args.input_usd_per_million, args.output_usd_per_million, args.budget_usd)
    if args.organizer_gateway:
        if (not args.real or not args.synthetic_rag or args.rag_dir is not None
                or args.scenario != ['macro-rate'] or args.max_requests != 1
                or args.max_input_tokens > 16000 or args.max_output_tokens > 1000
                or args.request_seconds > 60 or args.total_seconds > 60 or any(p is not None for p in prices)):
            parser.error('Organizer mode requires --real, --synthetic-rag, one macro-rate scenario, one request, limits <=16000/1000/60s and no USD flags')
        if not args.plan and not args.acknowledge_unknown_cost:
            parser.error('Organizer execution requires --acknowledge-unknown-cost')
    elif args.acknowledge_unknown_cost:
        parser.error('--acknowledge-unknown-cost requires --organizer-gateway')
    if args.real:
        if not args.allow_provider_host or not (args.plan or args.allow_rag_transfer):
            parser.error('Real mode requires provider host and --allow-rag-transfer')
        if not args.organizer_gateway and not all(prices):
            parser.error('USD real mode requires explicit prices and budget')
    return args


def configuration(args):
    config = dict(os.environ)
    if args.real:
        from dotenv import dotenv_values
        config = {**dotenv_values(BASE / '.env'), **config}
        url = urlsplit(config.get('LLM_BASE_URL') or '')
        if (url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment
                or url.port not in (None, 443) or url.hostname != args.allow_provider_host):
            raise ValueError('PROVIDER_NOT_EXPLICITLY_ALLOWED')
        if not config.get('LLM_API_KEY') or not config.get('LLM_MODEL'):
            raise ValueError('MISSING_LLM_CONFIGURATION')
        if config.get('AI_MODE') == 'demo':
            raise ValueError('AI_DISABLED_IN_DEMO')
        if args.organizer_gateway and (config['LLM_BASE_URL'].rstrip('/') not in ORGANIZER_URLS
                                       or config['LLM_MODEL'] != ORGANIZER_MODEL):
            raise ValueError('ORGANIZER_CONFIGURATION_MISMATCH')
    return config


def load_corpus(args, config):
    if args.synthetic_rag:
        return synthetic_chunks(), []
    directory = args.rag_dir or Path(config.get('RAG_KNOWLEDGE_BASE_DIR') or 'data/processed')
    if not directory.is_absolute():
        directory = BASE / directory
    files = sorted(directory.glob('*.json'))
    chunks = [chunk for file in files for chunk in load_chunks(str(file))]
    if not chunks or any(not isinstance(c.get('text'), str) or not c['text'].strip()
                         or not isinstance(c.get('source'), str) or not c['source']
                         or not isinstance(c.get('page'), int) or c['page'] < 1 for c in chunks):
        raise ValueError('MISSING_OR_INVALID_RAG_CORPUS')
    import hashlib
    return chunks, [{'file': file.name, 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()} for file in files]


def real_client(config):
    # Only reached after real preflight. No default SDK retries or redirect following.
    from openai import AsyncOpenAI, DefaultAsyncHttpxClient
    return AsyncOpenAI(api_key=config['LLM_API_KEY'], base_url=config['LLM_BASE_URL'],
        max_retries=0, timeout=60, http_client=DefaultAsyncHttpxClient(follow_redirects=False, trust_env=False))


async def complete_with_client(client, config, messages, *, max_tokens, timeout):
    """One SDK attempt, shared by single and paired evaluation only."""
    response = await client.with_options(timeout=timeout, max_retries=0).chat.completions.create(
        model=config['LLM_MODEL'], messages=messages, max_tokens=max_tokens)
    if not response.choices:
        raise ValueError('NO_MODEL_CHOICES')
    usage = response.usage
    return {'raw': response.choices[0].message.content or '',
            'finish_reason': response.choices[0].finish_reason, 'model': response.model,
            'usage': ({k: getattr(usage, k, None) for k in
                ('prompt_tokens', 'completion_tokens', 'total_tokens')} if usage else None)}


async def execute(args):
    cases = scenarios()
    if args.list:
        print(json.dumps([{'id': c['id'], 'category': c['category']} for c in cases], ensure_ascii=False))
        return 0
    cases = [c for c in cases if not args.scenario or c['id'] in args.scenario]
    config = configuration(args)
    secret = config.get('LLM_API_KEY', '') if args.real else ''
    chunks, corpus_files = load_corpus(args, config)
    limits = {'max_requests': args.max_requests, 'max_input_tokens': args.max_input_tokens,
              'max_output_tokens': args.max_output_tokens, 'request_seconds': args.request_seconds,
              'total_seconds': args.total_seconds,
              'billing_mode': 'organizer_rub_quota' if args.organizer_gateway else 'usd',
              'input_rate': None if args.organizer_gateway else args.input_usd_per_million or Decimal(0),
              'output_rate': None if args.organizer_gateway else args.output_usd_per_million or Decimal(0),
              'budget_usd': None if args.organizer_gateway else args.budget_usd or Decimal(0)}
    prepared, plan = make_plan(cases, chunks, limits)
    if args.real:
        validate_real_plan(plan)
    print(json.dumps({'mode': 'real' if args.real else 'fake', 'plan': plan}, default=str, ensure_ascii=False))
    if args.plan:
        return 0
    metadata = {'corpus_files': corpus_files, 'synthetic_rag': args.synthetic_rag,
                'requested_model': config.get('LLM_MODEL') if args.real else 'fake-no-llm',
                'provider_host': args.allow_provider_host if args.real else None,
                'unknown_cost_acknowledged': args.acknowledge_unknown_cost}
    if args.real and plan['planned_requests']:
        client = real_client(config)
        async def complete(messages, *, max_tokens, timeout):
            return await complete_with_client(client, config, messages, max_tokens=max_tokens, timeout=timeout)
        try:
            folder = await run(prepared, plan, complete, real=True, secret=secret, metadata=metadata)
        finally:
            await client.close()
    else:
        folder = await run(prepared, plan, metadata=metadata, real=args.real, secret=secret)
    summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    print(json.dumps({'results': str(folder), 'human_review_required': True,
                      'error_codes': summary.get('error_codes', {})}, ensure_ascii=False))
    return 1 if summary['stopped'] or any(s != 'RECEIVED' for s in summary['statuses'].values()) else 0


def main(argv=None):
    args = arguments(argv)
    try:
        return asyncio.run(execute(args))
    except KeyboardInterrupt:
        print('INTERRUPTED: inspect intent files; do not automatically retry real calls.')
        return 130
    except Exception as error:
        safe_codes = {'PRODUCTION_PROMPT_DRIFT', 'INPUT_LIMIT_EXCEEDED_NO_PROMPT_TRUNCATION',
            'REQUEST_OR_BUDGET_LIMIT_EXCEEDED', 'MISSING_OR_INVALID_RAG_CORPUS',
            'PROVIDER_NOT_EXPLICITLY_ALLOWED', 'MISSING_LLM_CONFIGURATION', 'AI_DISABLED_IN_DEMO',
            'ORGANIZER_CONFIGURATION_MISMATCH', 'INVALID_BILLING_MODE', 'INVALID_ORGANIZER_LIMITS'}
        print(json.dumps({'error': str(error) if isinstance(error, ValueError) and str(error) in safe_codes
                          else 'EVALUATION_ERROR_DETAILS_WITHHELD'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
