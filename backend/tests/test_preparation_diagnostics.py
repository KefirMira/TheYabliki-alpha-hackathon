import asyncio
import json
import pytest
from services import analysis_preparation_service as module
from test_analysis_preparation import setup_service

SENTINEL='SYNTHETIC-DIAGNOSTIC-SECRET'


@pytest.mark.parametrize('stage', [entry[0] for entry in module.PLAN])
def test_preparation_failure_has_safe_stage_without_retries(setup_service,monkeypatch,tmp_path,capsys,stage):
    service,state=setup_service
    calls=[]
    def fault(*args,**kwargs):
        calls.append(1)
        raise RuntimeError(SENTINEL)
    async def async_fault(*args,**kwargs):
        return fault()
    if stage=='load_snapshot':monkeypatch.setattr(module.CompanyRepository,'get_by_source_id',async_fault)
    elif stage=='company_context':service.context_loader=async_fault
    elif stage=='rag_search':service.corpus_loader=fault
    elif stage=='prepare_input':monkeypatch.setattr(module,'MAX_INPUT_BYTES',object())
    elif stage=='transfer_check':monkeypatch.setattr(module,'external_transfer_guard',fault)
    elif stage=='local_stub':
        digest=module.digest
        def digest_fault(value):
            if isinstance(value,dict) and value.get('relevance')=='unknown':return fault()
            return digest(value)
        monkeypatch.setattr(module,'digest',digest_fault)
    else:
        assemble=module.analyze_for_company_with_evidence
        async def break_after_stub(*args,**kwargs):
            await assemble(*args,**kwargs)
            fault()
        monkeypatch.setattr(module,'analyze_for_company_with_evidence',break_after_stub)
    report=asyncio.run(service.prepare('SYNTH-PREP',1))
    assert report.error_code=='PREPARATION_FAILED'
    assert report.diagnostic.stage==stage and report.diagnostic.retry_allowed is False
    assert report.diagnostic.family==('TYPE' if stage=='prepare_input' else 'RUNTIME')
    assert sum(step.status=='FAILED' for step in report.steps)==1
    assert state.connections==0 and len(calls)<2 and report.paid_calls==0
    assert SENTINEL not in report.model_dump_json()
    captured=capsys.readouterr()
    assert SENTINEL not in captured.out+captured.err
    (tmp_path/'diagnostic.json').write_text(report.diagnostic.model_dump_json(indent=2),encoding='utf-8')
