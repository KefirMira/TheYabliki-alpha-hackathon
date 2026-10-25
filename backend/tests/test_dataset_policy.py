import asyncio
import copy
import json
from unittest.mock import AsyncMock
import pytest
from services.dataset_analysis import (
    HackathonDatasetPolicy,DatasetDraftAdapter,LocalDatasetClient,sha,canonical,DatasetExternalDTO)
from services.external_context_policy import PolicyDenied
from services.company_context_service import external_transfer_guard,CompanyContextExternalTransferBlocked
from services.synthetic_gateway_input import make_input
from dataset_fixture import attributes,manifest

def test_original_guard_and_synthetic_dto_are_not_dataset_permission():
    with pytest.raises(CompanyContextExternalTransferBlocked):
        external_transfer_guard({})
    p=HackathonDatasetPolicy(manifest())
    with pytest.raises(PolicyDenied):
        p.verify(make_input((1,)))

def test_combination_approval_required():
    with pytest.raises(PolicyDenied):
        HackathonDatasetPolicy(manifest().model_copy(update={"combination_approved":False}))

@pytest.mark.parametrize("change",["hash","attributes","edited_id","missing_origin"])
def test_csv_provenance_denied(change):
    async def scenario():
        attrs=attributes()
        data={"_company_profile_csv_v1":{"source":"df_Uid_data_hack","current":{
            "file_sha256":"a"*64,"attributes":attrs}}}
        p=HackathonDatasetPolicy(manifest())
        if change=="hash":data["_company_profile_csv_v1"]["current"]["file_sha256"]="b"*64
        if change=="attributes":attrs["MAINOKVED_NAME"]="private-canary"
        if change=="edited_id":attrs["SYNTHETIC_U"]="other"
        if change=="missing_origin":data={}
        session=AsyncMock()
        session.scalar.return_value=data
        record=type("Record",(),{"id":1,"source_id":"SYNTH-COMPANY-A"})()
        with pytest.raises(PolicyDenied) as error:
            await p.load_context(session,record)
        assert "private-canary" not in str(error.value)
    asyncio.run(scenario())

def test_fake_only_payload_dto_and_minimization():
    async def scenario():
        attrs=attributes()
        p=HackathonDatasetPolicy(manifest())
        session=AsyncMock()
        session.scalar.return_value={"_company_profile_csv_v1":{"source":"df_Uid_data_hack","current":{
            "file_sha256":"a"*64,"attributes":attrs}}}
        record=type("Record",(),{"id":1,"source_id":"SYNTH-COMPANY-A"})()
        context=await p.load_context(session,record)
        dto,ev=p.prepare(context,"Учебная ключевая ставка и кредитование")
        body=dto.messages[1].content
        assert attrs["SYNTHETIC_U"] not in body and "GROUP_ID" not in body
        assert "123.45" in body and '"currency": null' in body and '"year": null' in body
        assert "payment_structure" not in json.loads(body)["company_source_assertions"]["computed"]
        adapter=DatasetDraftAdapter(LocalDatasetClient()).bind_policy(p)
        raw=await adapter.complete(dto)
        assert json.loads(raw)["relevance"]=="unknown"
        assert adapter.requests==1 and adapter.transport=="fake"
        with pytest.raises(Exception):
            await adapter.complete(dto)
        with pytest.raises(PolicyDenied):
            p.verify(dto.model_copy())
        assert ev[0].text==p.manifest.corpus[0]["text"]
        assert ev[0].provenance.publisher is None
        for news in ["", "secret@example.invalid", "Bearer very-secret-canary", "1"*5001]:
            with pytest.raises(PolicyDenied):
                p.prepare(context,news)
        context["facts"]["industry"]["value"]="tampered"
        with pytest.raises(PolicyDenied):
            p.prepare(context,"Учебная ставка")
    asyncio.run(scenario())


@pytest.mark.parametrize("kind",["length","empty","json","usage","tools","timeout","quota"])
def test_dataset_adapter_response_errors_never_repeat(kind):
    from types import SimpleNamespace
    from services.synthetic_draft_adapter import DraftStopped
    async def scenario():
        attrs=attributes()
        p=HackathonDatasetPolicy(manifest())
        session=AsyncMock()
        session.scalar.return_value={"_company_profile_csv_v1":{"source":"df_Uid_data_hack","current":{
            "file_sha256":"a"*64,"attributes":attrs}}}
        record=type("Record",(),{"id":1,"source_id":"SYNTH-COMPANY-A"})()
        context=await p.load_context(session,record)
        dto,_=p.prepare(context,"Учебная ключевая ставка")
        client=LocalDatasetClient()
        original=client.create
        calls=0
        async def broken(**kwargs):
            nonlocal calls
            calls+=1
            if kind=="timeout":raise TimeoutError()
            if kind=="quota":raise RuntimeError("Budget has been exceeded")
            response=await original(**kwargs)
            if kind=="length":response.choices[0].finish_reason="length"
            if kind=="empty":response.choices[0].message.content=""
            if kind=="json":response.choices[0].message.content="{"
            if kind=="usage":response.usage=None
            if kind=="tools":response.choices[0].message.tool_calls=[{"name":"send_secret"}]
            return response
        client.create=broken
        adapter=DatasetDraftAdapter(client).bind_policy(p)
        with pytest.raises(DraftStopped):
            await adapter.complete(dto)
        with pytest.raises(DraftStopped):
            await adapter.complete(dto)
        assert calls==1 and adapter.requests==1
    asyncio.run(scenario())
