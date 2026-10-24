"""Bounded sequential evaluation. No SQL, RSS, production service imports or retries."""
import asyncio
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import time
from uuid import uuid4

from evaluation.inputs import prepare
from evaluation.prompts import SOURCE_HASHES
from schemas.company import CompanyProfile
from services.structured_analysis_service import parse_structured_analysis
from services.validation_service import validate_analysis

OUTPUT_ROOT = Path(__file__).resolve().parents[1] / 'evaluation-results'
RUBRIC = ['factual_accuracy', 'company_alignment', 'recommendation_quality',
          'source_correctness', 'facts_vs_assumptions']


def token_bound(messages):
    # Conservative planning proxy, NOT the provider tokenizer or a billing guarantee.
    return sum(len(m['content'].encode('utf-8')) for m in messages) + 512


def estimate(input_tokens, output_tokens, input_rate, output_rate):
    return (Decimal(input_tokens) * input_rate + Decimal(output_tokens) * output_rate) / Decimal(1000000)


def technical_checks(raw, evidence, case, finish):
    result = {'schema_valid': False, 'finish_reason': finish, 'truncated': finish == 'length',
              'citation_ids_valid': None, 'citations_present': False,
              'heuristic_warnings': [], 'human_review_required': True,
              'factual_accuracy': 'NOT_ASSESSED'}
    analysis_text = raw
    try:
        parsed = parse_structured_analysis(raw)
        result['schema_valid'] = True
        analysis_text = '\n'.join([parsed.summary, *parsed.risks, *parsed.opportunities, *parsed.recommendations])
        result['heuristic_warnings'] = validate_analysis(
            analysis_text,
            CompanyProfile.model_validate(case['company']))
    except ValueError:
        result['schema_error'] = 'INVALID_ANALYSIS_JSON'
    ids = {e['id'] for e in evidence}
    cited = [int(i) for i in re.findall(r'\[Источник\s+(\d+)\]', analysis_text)]
    result['citations_present'] = bool(cited)
    result['citation_ids_valid'] = all(i in ids for i in cited) if cited else None
    # Existing retrieval scores measure search rank, never truth/confidence.
    return result


def sanitized(value, secret=''):
    if isinstance(value, str):
        if secret:
            value = value.replace(secret, '[REDACTED]')
        return re.sub(r'\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,})', '[REDACTED]', value)
    if isinstance(value, dict):
        return {k: sanitized(v, secret) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitized(v, secret) for v in value]
    return value


def write_json(path, data, secret=''):
    # Directories/files are private on POSIX; on Windows inherited ACLs still apply.
    with path.open('x', encoding='utf-8') as file:
        json.dump(sanitized(data, secret), file, ensure_ascii=False, indent=2, default=str)
        file.flush()
        os.fsync(file.fileno())
    path.chmod(0o600)


def make_plan(cases, chunks, limits):
    prepared = [(case, prepare(case, chunks)) for case in cases]
    total = Decimal(0)
    requests = 0
    for _, item in prepared:
        item['input_token_planning_bound'] = token_bound(item['messages'])
        if item['input_token_planning_bound'] > limits['max_input_tokens']:
            raise ValueError('INPUT_LIMIT_EXCEEDED_NO_PROMPT_TRUNCATION')
        if item['evidence']:
            requests += 1
            total += estimate(item['input_token_planning_bound'], limits['max_output_tokens'],
                              limits['input_rate'], limits['output_rate'])
    return prepared, {'scenario_count': len(cases), 'planned_requests': requests,
                      'estimated_upper_usd': str(total), 'limits': limits,
                      'pricing_note': 'Operator rates; byte-based planning bound; excludes unknown gateway fees.'}


async def fake_complete(messages, *, max_tokens, timeout):
    return {'raw': json.dumps({'relevance': 'unknown',
        'summary': 'Синтетический fake-ответ для проверки инструмента; не оценка качества модели.',
        'risks': [], 'opportunities': [], 'recommendations': []}, ensure_ascii=False),
        'finish_reason': 'stop', 'model': 'fake-no-llm', 'usage': None}


async def run(prepared, plan, complete=fake_complete, *, real=False, secret='', metadata=None, root=OUTPUT_ROOT):
    if real and (plan['planned_requests'] > plan['limits']['max_requests'] or
                 Decimal(plan['estimated_upper_usd']) > plan['limits']['budget_usd']):
        raise ValueError('REQUEST_OR_BUDGET_LIMIT_EXCEEDED')
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder = root / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex)
    folder.mkdir(mode=0o700)
    write_json(folder / 'manifest.json', {'mode': 'real' if real else 'fake', 'plan': plan,
        'metadata': metadata or {}, 'prompt_source_hashes': SOURCE_HASHES,
        'corpus_fingerprint': hashlib.sha256(json.dumps([i['evidence'] for _, i in prepared],
            ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        'warning': 'JSON validation is not evidence of factual correctness; human review required.'}, secret)
    rows = []
    started = time.monotonic()
    stop = False
    actual_cost = Decimal(0)
    attempted = 0
    billing_unknown = False
    for case, item in prepared:
        record = {'scenario': case, 'request': item, 'mode': 'real' if real else 'fake',
                  'status': 'NOT_ATTEMPTED', 'response': None, 'checks': None,
                  'elapsed_seconds': 0, 'provider_outcome': 'NOT_SENT'}
        if not item['evidence']:
            record['status'] = 'NO_RAG_CONTEXT'
        elif not stop:
            remaining = plan['limits']['total_seconds'] - (time.monotonic() - started)
            timeout = min(plan['limits']['request_seconds'], remaining)
            if timeout <= 0 or (real and attempted >= plan['limits']['max_requests']):
                stop = True
            else:
                attempted += 1
                call_start = time.monotonic()
                # Persist intent BEFORE sending. A crash must never invite an automatic retry.
                write_json(folder / f"{case['id']}.intent.json", {'scenario_id': case['id'],
                    'mode': record['mode'], 'provider_outcome': 'POSSIBLY_SENT_DO_NOT_AUTO_RETRY'}, secret)
                try:
                    async with asyncio.timeout(timeout):
                        response = await complete(item['messages'],
                            max_tokens=plan['limits']['max_output_tokens'], timeout=timeout)
                    record['response'] = response
                    record['provider_outcome'] = 'RESPONSE_RECEIVED'
                    record['status'] = 'RECEIVED'
                    record['checks'] = technical_checks(response['raw'], item['evidence'], case, response['finish_reason'])
                    usage = response.get('usage')
                    if real:
                        if not usage or any(not isinstance(usage.get(k), int) or isinstance(usage[k], bool) or usage[k] < 0
                                            for k in ('prompt_tokens', 'completion_tokens')):
                            stop = True
                            record['cost_status'] = 'UNKNOWN_STOPPED'
                            billing_unknown = True
                        else:
                            cost = estimate(usage['prompt_tokens'], usage['completion_tokens'],
                                            plan['limits']['input_rate'], plan['limits']['output_rate'])
                            actual_cost += cost
                            record['estimated_actual_usd'] = str(cost)
                            if actual_cost >= plan['limits']['budget_usd'] or usage['prompt_tokens'] > item['input_token_planning_bound'] or usage['completion_tokens'] > plan['limits']['max_output_tokens']:
                                stop = True
                                record['cost_status'] = 'BOUND_REACHED_STOPPED'
                except Exception:
                    # Do not persist provider exception messages, request headers or bodies.
                    record['status'] = 'ERROR_NO_RETRY'
                    record['provider_outcome'] = 'UNKNOWN_DO_NOT_AUTO_RETRY' if real else 'FAKE_ERROR'
                    billing_unknown |= real
                    stop = True
                finally:
                    record['elapsed_seconds'] = round(time.monotonic() - call_start, 4)
        write_json(folder / f"{case['id']}.json", record, secret)
        rows.append({'scenario_id': case['id'], 'category': case['category'], 'mode': record['mode'],
                     'status': record['status'], 'review_expectation': case['review_expectation'],
                     **{key: '' for key in RUBRIC}, 'reviewer': '', 'notes': ''})
    with (folder / 'manual-review.tsv').open('x', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), delimiter='\t')
        writer.writeheader()
        writer.writerows(sanitized(rows, secret))
    (folder / 'manual-review.tsv').chmod(0o600)
    write_json(folder / 'summary.json', {'attempted': attempted, 'mode': 'real' if real else 'fake',
        'stopped': stop, 'estimated_actual_usd': None if billing_unknown else str(actual_cost) if real else '0',
        'known_usage_estimated_usd': str(actual_cost), 'billing_complete': not billing_unknown,
        'elapsed_seconds': round(time.monotonic() - started, 4),
        'statuses': {r['scenario_id']: r['status'] for r in rows}}, secret)
    return folder
