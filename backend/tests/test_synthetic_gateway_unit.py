import asyncio
import json
import pytest
from pydantic import ValidationError
from services import synthetic_gateway_input as inputs
from services.synthetic_draft_adapter import SyntheticDraftAdapter, DraftLimits, DraftStopped, MODEL
from schemas.orchestration import OrchestrationTrace,GatewayOrchestrationTrace
from synthetic_gateway_fixture import FakeClient,response


def test_closed_dto_and_pin_ignore_callers_flags_and_db_fields(monkeypatch):
    dto=inputs.make_input([1,2])
    assert len(inputs.verify_input(dto))==64
    with pytest.raises(ValidationError):
        inputs.SyntheticDraftInput(**dto.model_dump(),synthetic=True,db_context={})
    for bad in [dto.model_copy(update={'fixture_sha256':'0'*64}),
                dto.model_copy(update={'messages':()}),dto.model_copy(update={'chunk_ids':(999,)})]:
        with pytest.raises(ValueError):inputs.verify_input(bad)
    monkeypatch.setattr(inputs,'FIXTURE_SHA256','0'*64)
    with pytest.raises(ValueError,match='MANIFEST_CHANGED'):inputs.make_input([1])


@pytest.mark.parametrize('ids',[[],[1,1],[999],[True],['1']])
def test_invalid_sources(ids):
    with pytest.raises(ValueError):inputs.make_input(ids)


@pytest.mark.parametrize('limits',[{'max_requests':2},{'max_output_tokens':2001},
    {'max_input_tokens':8001},{'request_seconds':61},{'max_requests':True}])
def test_limits_fail_closed(limits):
    with pytest.raises(ValidationError):DraftLimits(**limits)


def test_defaults_and_original_local_trace_contract():
    assert DraftLimits().max_output_tokens==1000
    assert DraftLimits(max_output_tokens=2000).max_requests==1
    with pytest.raises(ValidationError):OrchestrationTrace(paid_calls=1)
    with pytest.raises(ValidationError):GatewayOrchestrationTrace(transport='fake',sdk_requests=1,paid_calls=1)


@pytest.mark.parametrize('options',[{}, {'allow_real':True},
    {'allow_real':True,'acknowledge_unknown_cost':True,'base_url':'https://other.invalid/v1'},
    {'allow_real':True,'acknowledge_unknown_cost':True,'model':'other'}])
def test_no_sdk_import_or_implicit_enablement(options):
    with pytest.raises(DraftStopped,match='AUTHORIZATION_REQUIRED'):
        SyntheticDraftAdapter.organizer(api_key='synthetic-not-real',**options)


def test_organizer_factory_and_mode_recheck_use_only_fake_sdk(monkeypatch):
    import sys
    from types import SimpleNamespace
    client=FakeClient()
    captured={}
    def factory(**options):
        captured.update(options)
        return client
    monkeypatch.setitem(sys.modules,'openai',SimpleNamespace(AsyncOpenAI=factory,DefaultAsyncHttpxClient=lambda **kw:kw))
    monkeypatch.setenv('AI_MODE','demo')
    with pytest.raises(DraftStopped,match='AI_DISABLED_IN_DEMO'):
        SyntheticDraftAdapter.organizer(api_key='synthetic-not-real',allow_real=True,acknowledge_unknown_cost=True)
    assert captured=={}
    monkeypatch.setenv('AI_MODE','full')
    adapter=SyntheticDraftAdapter.organizer(api_key='synthetic-not-real',allow_real=True,acknowledge_unknown_cost=True)
    assert captured['max_retries']==0 and captured['timeout']==60
    assert captured['http_client']=={'follow_redirects':False,'trust_env':False}
    assert adapter.transport=='organizer'
    monkeypatch.setenv('AI_MODE','demo')
    with pytest.raises(DraftStopped,match='AI_DISABLED_IN_DEMO'):
        asyncio.run(adapter.complete(inputs.make_input([1])))
    assert client.calls==[]


def test_one_call_parameters_accounting_and_repeat_denied():
    async def scenario():
        client=FakeClient()
        adapter=SyntheticDraftAdapter(client,limits=DraftLimits(max_output_tokens=2000))
        raw=await adapter.complete(inputs.make_input([1,2]))
        assert json.loads(raw)['relevance']=='medium'
        assert adapter.outcome=='RESPONSE_VALIDATED' and adapter.usage['reasoning_tokens']==500
        assert client.calls[0]['model']==MODEL and client.calls[0]['max_tokens']==2000
        with pytest.raises(DraftStopped,match='REQUEST_LIMIT'):await adapter.complete(inputs.make_input([1]))
        assert len(client.calls)==1
    asyncio.run(scenario())


@pytest.mark.parametrize('case,code',[
    ('timeout','TIMEOUT_UNKNOWN'),('network','REQUEST_UNKNOWN'),('quota','QUOTA_EXCEEDED'),
    ('usage','USAGE_UNKNOWN'),('length','RESPONSE_INCOMPLETE'),('empty','EMPTY_OR_LARGE'),
    ('json','JSON_INVALID'),('extra','JSON_INVALID'),('duplicate','JSON_INVALID'),
    ('tool','TOOL_CALL_FORBIDDEN'),('tokens','USAGE_LIMIT'),('reasoning','USAGE_UNKNOWN')])
def test_failures_never_retry_or_expose_error(case,code):
    async def scenario():
        value=response()
        message=value['choices'][0]['message']
        if case=='timeout':value=TimeoutError('sensitive-error-marker')
        if case=='network':value=OSError('sensitive-error-marker')
        if case=='quota':value=RuntimeError('Budget has been exceeded sensitive-error-marker')
        if case=='usage':value['usage']=None
        if case=='length':value['choices'][0]['finish_reason']='length'
        if case=='empty':message['content']=''
        if case=='json':message['content']='{'
        if case=='extra':message['content']=message['content'][:-1]+',"tool":"SQL"}'
        if case=='duplicate':message['content']=message['content'][:-1]+',"summary":"duplicate"}'
        if case=='tool':message['tool_calls']=[{'name':'arbitrary'}]
        if case=='tokens':value['usage']['completion_tokens']=1001
        if case=='reasoning':value['usage']['completion_tokens_details']['reasoning_tokens']=True
        client=FakeClient(value)
        adapter=SyntheticDraftAdapter(client)
        with pytest.raises(DraftStopped,match=code) as error:await adapter.complete(inputs.make_input([1]))
        assert 'sensitive-error-marker' not in str(error.value)
        assert adapter.outcome=='UNKNOWN'
        with pytest.raises(DraftStopped,match='REQUEST_LIMIT'):await adapter.complete(inputs.make_input([1]))
        assert len(client.calls)==1
    asyncio.run(scenario())


def test_provenance_and_input_bound_reject_before_sdk():
    async def scenario():
        for tamper in [True,False]:
            client=FakeClient()
            adapter=SyntheticDraftAdapter(client,limits=DraftLimits(max_input_tokens=1) if not tamper else None)
            dto=inputs.make_input([1])
            if tamper:dto=dto.model_copy(update={'messages':()})
            with pytest.raises(DraftStopped):await adapter.complete(dto)
            assert client.calls==[] and adapter.requests==0 and adapter.outcome=='NOT_SENT'
    asyncio.run(scenario())
