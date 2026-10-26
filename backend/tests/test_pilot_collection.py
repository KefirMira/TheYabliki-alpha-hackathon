"""Eight fixture-only fake SDK scenarios; never constructs a real client."""
import asyncio
import copy
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from evaluation.pilot_collection import fake_record, FakeSDK
from pilot_collection_demo import approved_records
from services.pilot_collection_input import (registry,preflight,make_collection_input,
    verify_collection_input,CollectionDraftAdapter,CollectionDraftInput,INPUTS_SHA256)
from services.pilot_collection_records import validate_record,CaptureClient,prepare_record
from services.synthetic_draft_adapter import DraftLimits,DraftStopped
from services.synthetic_gateway_input import make_input,verify_input

IDS=[s['scenario_id'] for s in registry()['scenarios']]


@pytest.mark.parametrize('scenario_id',IDS)
def test_each_scenario_fake_once_has_original_messages_sources_review_and_trace(scenario_id):
    record=asyncio.run(fake_record(scenario_id))
    bundle=validate_record(record,require_real=False)
    assert record['mode']=='FAKE_TEST_ONLY'
    assert bundle.model_name=='fake-collection-sdk-v1'
    assert record['orchestration']['sdk_requests']==1
    assert record['orchestration']['paid_calls']==0
    assert record['original_response']['content']==json.dumps(record['normalized'],ensure_ascii=False)
    assert record['request']['messages']==[m.model_dump() for m in make_collection_input(scenario_id).messages]
    assert record['plan']['input_allowance']<=8000
    assert bundle.financial_review.financial_correctness=='UNKNOWN'
    assert bundle.analysis.validation.passed is False
    assert 'FAKE_SDK_TEST_ONLY_NOT_LLM_RESULT' in bundle.analysis.validation.warnings
    with pytest.raises(ValueError,match='FAKE_RECORD'):validate_record(record)


@pytest.mark.parametrize('target',['messages','raw','source','review','usage'])
def test_record_tampering_rejected(target):
    record=asyncio.run(fake_record('metal-rate'))
    if target=='messages':record['request']['messages'][1]['content']+=' changed'
    if target=='raw':record['original_response']['content']+=' '
    if target=='source':record['normalized']['summary']='Unsupported [Источник 99]'
    if target=='review':record['financial_review']['findings']=[]
    if target=='usage':record['original_response']['usage']['total_tokens']+=1
    with pytest.raises(ValueError):validate_record(record,require_real=False)


def test_dto_copy_db_context_unknown_scenario_and_legacy_separation():
    dto=make_collection_input('metal-rate')
    with pytest.raises(ValueError):make_collection_input('SYNTH-UNAPPROVED-DB-ID')
    with pytest.raises(ValueError):verify_collection_input(dto.model_copy(update={'messages':make_collection_input('retail-demand').messages}))
    with pytest.raises(ValueError):verify_collection_input(dto.model_dump())
    with pytest.raises(ValueError):verify_collection_input(make_input((1,2)))
    assert verify_input(make_input((1,2)))=='8b218f5f668e0874895b606644f462ce39fdd5fd55b3309e0a8597998f36fa55'


@pytest.mark.parametrize('failure',['timeout','invalid_json','length','no_usage','network'])
def test_no_retries_and_no_publishable_record_on_failure(failure):
    class Broken(FakeSDK):
        async def create(self,**kwargs):
            if failure=='timeout':self.calls+=1;raise TimeoutError()
            if failure=='network':self.calls+=1;raise OSError('secret must not leak')
            value=await super().create(**kwargs)
            if failure=='invalid_json':value['choices'][0]['message']['content']='bad'
            if failure=='length':value['choices'][0]['finish_reason']='length'
            if failure=='no_usage':value.pop('usage')
            return value
    client=Broken('metal-rate');capture=CaptureClient(client)
    adapter=CollectionDraftAdapter(capture,limits=DraftLimits(max_output_tokens=2000))
    with pytest.raises(DraftStopped) as error:asyncio.run(prepare_record('metal-rate',adapter,capture))
    assert client.calls==1 and adapter.requests==1
    assert 'secret' not in str(error.value)
    with pytest.raises((DraftStopped,ValueError)):asyncio.run(prepare_record('metal-rate',adapter,capture))
    assert client.calls==1


def test_no_release_default_and_fake_release_never_approved(tmp_path,monkeypatch):
    assert len(approved_records())==8
    monkeypatch.setattr('pilot_collection_demo.RELEASE_SHA256',None)
    path=tmp_path/'release.json';path.write_text('{}')
    monkeypatch.setattr('pilot_collection_demo.RELEASE',path)
    with pytest.raises(ValueError,match='NOT_APPROVED'):approved_records()


def test_sources_are_short_attributed_public_historical_excerpts_not_bank_pdfs():
    data=registry();assert len(data['companies'])==3 and len(data['scenarios'])==8
    for s in data['sources']:
        assert s['url'].startswith('https://') and s['origin_format']=='HTML'
        assert s['export_format']=='TXT' and len(s['text'].split())<=25
        assert s['page_is_exported_excerpt'] is True
        assert s['publisher']!='Альфа-Банк'
    unknown=[s for s in data['sources'] if s['date'] is None]
    assert [s['key'] for s in unknown]==['msp-leasing']


def test_fake_import_cannot_target_public_demo_database():
    from pilot_collection_demo import _apply_records
    value='postgresql+asyncpg://synthetic:'+'a'*32+'@127.0.0.1:5432/test_saved_pilot_demo'
    with pytest.raises(ValueError,match='DEDICATED_FAKE_TEST_DATABASE'):
        asyncio.run(_apply_records(value,'test_saved_pilot_demo','Synthetic-password',[],fake_test=True))


def test_fake_normalized_output_and_messages_repeat_without_claiming_real_usage():
    first=asyncio.run(fake_record('production-fx-equipment'))
    second=asyncio.run(fake_record('production-fx-equipment'))
    assert first['request']==second['request'] and first['normalized']==second['normalized']
    assert first['financial_review']==second['financial_review']
    assert first['mode']==second['mode']=='FAKE_TEST_ONLY'


def test_even_pinned_fake_export_is_not_a_real_release(tmp_path,monkeypatch):
    from services.pilot_collection_input import digest
    record=asyncio.run(fake_record('metal-rate'))
    data={'records':[asyncio.run(fake_record(s)) for s in IDS]};path=tmp_path/'release.json';path.write_text(json.dumps(data))
    monkeypatch.setattr('pilot_collection_demo.RELEASE',path)
    monkeypatch.setattr('pilot_collection_demo.RELEASE_SHA256',digest(data))
    with pytest.raises(ValueError,match='FAKE_RECORD'):approved_records()


def test_valid_json_with_unknown_source_is_rejected_without_retry():
    class WrongCitation(FakeSDK):
        async def create(self,**kwargs):
            result=await super().create(**kwargs)
            content=json.loads(result['choices'][0]['message']['content'])
            content['summary']='Unsupported [Источник 99]'
            result['choices'][0]['message']['content']=json.dumps(content)
            return result
    client=WrongCitation('metal-rate');capture=CaptureClient(client)
    adapter=CollectionDraftAdapter(capture,limits=DraftLimits(max_output_tokens=2000))
    with pytest.raises(ValueError,match='SOURCE_REFERENCE_INVALID'):
        asyncio.run(prepare_record('metal-rate',adapter,capture))
    assert client.calls==1


@pytest.mark.parametrize('scenario_id',['retail-inflation','retail-demand','retail-logistics','production-fx-equipment','production-support'])
def test_collection_4000_is_explicit_pinned_and_single_call(scenario_id):
    from services.pilot_collection_input import CollectionDraftLimits
    from pydantic import ValidationError
    class CheckedSDK(FakeSDK):
        async def create(self,**kwargs):
            assert kwargs['max_tokens']==4000
            assert kwargs['messages']==[m.model_dump() for m in make_collection_input(scenario_id).messages]
            result=await super().create(**kwargs)
            result['usage']={'prompt_tokens':1000,'completion_tokens':3000,'total_tokens':4000,'completion_tokens_details':{'reasoning_tokens':2000}}
            return result
    client=CheckedSDK(scenario_id);capture=CaptureClient(client)
    adapter=CollectionDraftAdapter(capture,limits=CollectionDraftLimits(max_output_tokens=4000))
    record=asyncio.run(prepare_record(scenario_id,adapter,capture))
    assert record['request']['max_tokens']==record['plan']['max_output_tokens']==4000
    assert record['plan']['dto_sha256']==preflight(scenario_id)['dto_sha256']
    validate_record(record,require_real=False)
    with pytest.raises(ValueError):asyncio.run(prepare_record(scenario_id,adapter,capture))
    assert client.calls==1
    assert DraftLimits().max_output_tokens==1000
    assert CollectionDraftLimits().max_output_tokens==2000
    with pytest.raises(ValidationError):DraftLimits(max_output_tokens=4000)
    with pytest.raises(ValidationError):CollectionDraftLimits(max_output_tokens=4001)


@pytest.mark.parametrize('failure',['length','timeout','no_usage','invalid_json'])
def test_collection_4000_stops_without_retry(failure):
    from services.pilot_collection_input import CollectionDraftLimits
    class BrokenSDK(FakeSDK):
        async def create(self,**kwargs):
            if failure=='timeout':self.calls+=1;raise TimeoutError()
            value=await super().create(**kwargs)
            if failure=='length':value['choices'][0]['finish_reason']='length'
            if failure=='no_usage':value.pop('usage')
            if failure=='invalid_json':value['choices'][0]['message']['content']='{'
            return value
    client=BrokenSDK('retail-inflation');capture=CaptureClient(client)
    adapter=CollectionDraftAdapter(capture,limits=CollectionDraftLimits(max_output_tokens=4000))
    with pytest.raises(DraftStopped):asyncio.run(prepare_record('retail-inflation',adapter,capture))
    with pytest.raises(ValueError):asyncio.run(prepare_record('retail-inflation',adapter,capture))
    assert client.calls==1


def test_approved_release_has_exactly_eight_complete_real_records_and_pinned_legacy():
    from saved_pilot_demo import approved
    records=approved_records()
    assert len(records)==8 and {r['scenario_id'] for r in records}==set(IDS)
    for r in records:
        assert r['original_response']['finish_reason']=='stop'
        assert r['mode']=='REAL_SYNTHETIC'
        assert r['generation_metadata']['finish_reason']=='stop'
        assert r['expert_review']['financial_correctness']=='UNKNOWN'
        validate_record(r,require_real=True)
    assert next(r for r in records if r['scenario_id']=='retail-inflation')['request']['max_tokens']==4000
    data,bundle=approved()
    assert len(bundle.financial_review.findings)==20
