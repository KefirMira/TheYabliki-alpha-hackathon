"""Record construction/validation shared by fake preparation and later approved export.

No real client construction here. Fake records are explicitly non-releaseable.
"""
import asyncio
import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from schemas.analysis import AnalysisContent
from schemas.orchestration import GatewayOrchestrationTrace, TraceEvent
from schemas.persisted_analysis import PersistableAnalysis
from services.financial_review_service import review_financial_analysis
from services.synthetic_draft_adapter import field, MODEL, BASE_URL
from services.pilot_collection_input import (CollectionDraftAdapter, make_collection_input,
    verify_collection_input, scenario_input, digest, PROMPT_VERSION, preflight)


class CaptureClient:
    """Allowlisted SDK response projection: no headers, key or reasoning text."""
    def __init__(self, client):
        self.client = client
        self.chat = self.completions = self
        self.response = None
        self.options = {}
    def with_options(self, **options):
        self.options = options
        return self
    async def create(self, **kwargs):
        response = await self.client.with_options(**self.options).chat.completions.create(**kwargs)
        choices = field(response, 'choices') or []
        choice = choices[0] if choices else None
        usage = field(response, 'usage')
        self.response = {'provider_model':field(response,'model'),
            'response_id':field(response,'id'),
            'content':field(field(choice,'message'),'content'),
            'finish_reason':field(choice,'finish_reason'),
            'usage':{k:field(usage,k) for k in ('prompt_tokens','completion_tokens','total_tokens')}}
        details = field(usage,'completion_tokens_details')
        self.response['usage']['reasoning_tokens'] = field(details,'reasoning_tokens')
        return response
    async def close(self):
        await self.client.close()


def make_bundle(record):
    scenario, company, evidence = scenario_input(record['scenario_id'])
    content = AnalysisContent.model_validate(record['normalized'], strict=True)
    if record['normalized'] != json.loads(record['original_response']['content']):
        raise ValueError('MODEL_CONTENT_CHANGED')
    cites = set(map(int,re.findall(r'\[Источник\s+(\d+)\]', ' '.join(
        [content.summary,*content.risks,*content.opportunities,*content.recommendations]))))
    if not cites or not cites <= {e['id'] for e in evidence}:
        raise ValueError('SOURCE_REFERENCE_INVALID')
    review = review_financial_analysis(content, company['context'], evidence, scenario['news'])
    if review.blocking:
        raise ValueError('FINANCIAL_REVIEW_BLOCKER')
    sources = [{k:e[k] for k in ('id','document','page','score')} for e in evidence]
    return PersistableAnalysis.model_validate({'analysis':dict(company_id=company['source_id'],
        news=scenario['news'], **content.model_dump(), sources=sources,
        validation={'passed':False,'warnings':['SYNTHETIC_COMPANY_HYPOTHETICAL_NEWS',
            'FACTUAL_ACCURACY_NOT_ASSESSED','HISTORICAL_PUBLIC_EXCERPTS','HUMAN_REVIEW_REQUIRED'] +
            (['FAKE_SDK_TEST_ONLY_NOT_LLM_RESULT'] if record['mode']=='FAKE_TEST_ONLY' else [])}),
        'evidence':evidence,'model_name':record['model'],'prompt_version':PROMPT_VERSION,
        'financial_review':review,'orchestration':record['orchestration']})


async def prepare_record(scenario_id, adapter, capture):
    if type(adapter) is not CollectionDraftAdapter or type(capture) is not CaptureClient:
        raise ValueError('BOUNDED_COLLECTION_ADAPTER_REQUIRED')
    if (adapter.limits.max_output_tokens not in (2000,4000) or adapter.limits.max_input_tokens!=8000
            or adapter.limits.request_seconds!=60):
        raise ValueError('APPROVED_LIMITS_REQUIRED')
    if adapter._client is not capture or adapter.requests:
        raise ValueError('FRESH_CAPTURE_ADAPTER_REQUIRED')
    dto = make_collection_input(scenario_id)
    plan = preflight(scenario_id)
    plan["max_output_tokens"] = adapter.limits.max_output_tokens
    async with asyncio.timeout(120):
        raw = await adapter.complete(dto)
    trace = GatewayOrchestrationTrace(status='VALIDATED', decisions=2, drafts=1, reviews=1,
        transport=adapter.transport, sdk_requests=adapter.requests,
        paid_calls=adapter.requests if adapter.transport=='organizer' else 0,
        outbound_sha256=adapter.outbound_sha256, usage=adapter.usage,
        finish_reason=adapter.finish_reason, request_outcome=adapter.outcome,
        elapsed_ms=adapter.elapsed_ms, events=[
            TraceEvent(tool='PREPARE',reason='PINNED_SCENARIO_VERIFIED'),
            TraceEvent(tool='DECIDE',reason='FIXTURE_DRAFT_SELECTED'),
            TraceEvent(tool='DRAFT',reason='BOUNDED_SDK_RESPONSE'),
            TraceEvent(tool='VALIDATE',reason='JSON_AND_PROVENANCE_CHECKED'),
            TraceEvent(tool='REVIEW',reason='DETERMINISTIC_FINANCIAL_REVIEW'),
            TraceEvent(tool='DECIDE',reason='HUMAN_REVIEW_REQUIRED')])
    record = {'scenario_id':scenario_id,'mode':'REAL_SYNTHETIC' if adapter.transport=='organizer' else 'FAKE_TEST_ONLY',
        'model':MODEL if adapter.transport=='organizer' else 'fake-collection-sdk-v1',
        'transport':adapter.transport,'generated_at':datetime.now(timezone.utc).isoformat(),
        'plan':plan,'request':{'model':MODEL,'max_tokens':adapter.limits.max_output_tokens,
            'messages':[m.model_dump() for m in dto.messages]},
        'original_response':copy.deepcopy(capture.response), 'normalized':json.loads(raw),
        'content_sha256':hashlib.sha256(raw.encode()).hexdigest(),
        'orchestration':trace.model_dump(mode='json')}
    bundle = make_bundle(record)
    record['financial_review'] = bundle.financial_review.model_dump(mode='json')
    validate_record(record, require_real=False)
    return record


def validate_record(record, *, require_real=True):
    scenario_id = record['scenario_id']
    dto = make_collection_input(scenario_id)
    expected_plan = preflight(scenario_id)
    expected_plan['max_output_tokens'] = record['request']['max_tokens']
    if record['plan'] != expected_plan:
        raise ValueError('RECORD_PREFLIGHT_CHANGED')
    if record['request']['messages'] != [m.model_dump() for m in dto.messages]:
        raise ValueError('RECORD_MESSAGES_CHANGED')
    if record['request']['model'] != MODEL or record['request']['max_tokens'] not in (2000,4000):
        raise ValueError('RECORD_MODEL_OR_LIMIT_CHANGED')
    raw = record['original_response']['content']
    if record['content_sha256'] != hashlib.sha256(raw.encode()).hexdigest():
        raise ValueError('RECORD_CONTENT_CHANGED')
    trace = GatewayOrchestrationTrace.model_validate(record['orchestration'])
    if (trace.outbound_sha256 != verify_collection_input(dto) or trace.sdk_requests != 1
            or trace.finish_reason != 'stop' or trace.request_outcome != 'RESPONSE_VALIDATED'
            or not trace.usage or record['original_response']['finish_reason'] != 'stop'):
        raise ValueError('RECORD_TRACE_INVALID')
    if require_real and (record['mode']!='REAL_SYNTHETIC' or record['transport']!='organizer'
            or record['model']!=MODEL or trace.transport!='organizer' or trace.paid_calls!=1):
        raise ValueError('FAKE_RECORD_CANNOT_BE_RELEASED')
    expected_usage={k:v for k,v in record['original_response']['usage'].items() if v is not None}
    if (trace.usage!=expected_usage or any(type(v) is not int or v<0 for v in expected_usage.values())
            or expected_usage['prompt_tokens']>8000 or expected_usage['completion_tokens']>record['request']['max_tokens']
            or expected_usage['total_tokens']!=expected_usage['prompt_tokens']+expected_usage['completion_tokens']):
        raise ValueError('RECORD_USAGE_INVALID')
    if record['mode']=='FAKE_TEST_ONLY' and (trace.paid_calls or record['transport']!='fake'):
        raise ValueError('FAKE_ACCOUNTING_INVALID')
    datetime.fromisoformat(record['generated_at'])
    bundle = make_bundle(record)
    if record['financial_review'] != bundle.financial_review.model_dump(mode='json'):
        raise ValueError('FINANCIAL_REVIEW_CHANGED')
    return bundle
