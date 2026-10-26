import json
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from main import app
from api import live_synthetic as live
from api.auth import company_read
from services.pilot_collection_input import CollectionDraftLimits

METAL='SYNTH-COLLECTION-METAL'
class Fake:
    def __init__(self,failure=None):self.chat=self.completions=self;self.calls=0;self.failure=failure
    def with_options(self,**kw):assert kw=={'max_retries':0,'timeout':60};return self
    async def create(self,**kw):
        self.calls+=1
        assert kw['model']==live.MODEL and kw['max_tokens']==4000
        assert 'Синтетическое металлургическое производство' in kw['messages'][1]['content']
        if self.failure=='timeout':raise TimeoutError()
        content=json.dumps({'relevance':'medium','summary':'Учебный условный вывод.','risks':['Условный риск, величина неизвестна.'],'opportunities':['Условная возможность.'],'recommendations':['Уточнить исходные данные.']},ensure_ascii=False)
        result={'model':live.MODEL,'choices':[{'finish_reason':'stop','message':{'content':content}}],'usage':{'prompt_tokens':1000,'completion_tokens':100,'total_tokens':1100,'completion_tokens_details':{'reasoning_tokens':0}}}
        if self.failure=='length':result['choices'][0]['finish_reason']='length'
        if self.failure=='json':result['choices'][0]['message']['content']='{'
        if self.failure=='usage':result.pop('usage')
        return result
    async def close(self):pass

@pytest.fixture
def configured(monkeypatch):
    for k,v in {'LIVE_SYNTHETIC_ANALYSIS_ENABLED':'true','SAVED_PILOT_OFFLINE':'0','AI_MODE':'full','LLM_API_KEY':'synthetic-local-test-key','LLM_MODEL':live.MODEL,'LLM_BASE_URL':live.BASE_URL,'LIVE_SYNTHETIC_MAX_REQUESTS':'3'}.items():monkeypatch.setenv(k,v)
    live._used.clear();live._active.clear()
    async def scoped(source_id):
        if source_id!=METAL:raise HTTPException(403,detail={'code':'ACCESS_DENIED'})
        return SimpleNamespace(user_id='synthetic-test-actor')
    app.dependency_overrides[company_read]=scoped
    yield
    app.dependency_overrides.clear();live._used.clear();live._active.clear()

def body():return {'request_id':str(uuid4()),'title':'Учебный заголовок','text':'Предположим рост стоимости сырья.','external_transfer_confirmed':True,'url':'https://example.org/user-news'}

def test_allowed_readonly_transient_one_call_and_duplicate_reservation(configured,monkeypatch):
    fake=Fake();monkeypatch.setattr(live,'get_adapter',lambda:live.ManualAdapter(fake,limits=CollectionDraftLimits(max_output_tokens=4000)))
    with TestClient(app) as c:
        assert c.get('/api/companies/'+METAL+'/live-synthetic/status').json()['enabled'] is True
        request=body();r=c.post('/api/companies/'+METAL+'/live-synthetic/analyses',json=request)
        assert r.status_code==200,r.text
        d=r.json();assert d['persisted'] is False and d['analysis']['sources']==[] and d['usage']['total_tokens']==1100
        assert d['trace']['sdk_requests']==1 and d['analysis']['validation']['passed'] is False
        assert c.post('/api/companies/'+METAL+'/live-synthetic/analyses',json=request).status_code==409
        assert fake.calls==1
        assert c.post('/api/companies/SYNTH-COLLECTION-RETAIL/live-synthetic/analyses',json=body()).status_code==403

@pytest.mark.parametrize('setting,value',[('LIVE_SYNTHETIC_ANALYSIS_ENABLED','false'),('LLM_API_KEY',''),('SAVED_PILOT_OFFLINE','1'),('AI_MODE','demo'),('LLM_BASE_URL','https://example.org'),('LLM_MODEL','other')])
def test_disabled_fails_before_sdk(configured,monkeypatch,setting,value):
    monkeypatch.setenv(setting,value)
    def forbidden():raise AssertionError('SDK must not be created')
    monkeypatch.setattr(live,'get_adapter',forbidden)
    with TestClient(app) as c:assert c.post('/api/companies/'+METAL+'/live-synthetic/analyses',json=body()).status_code==503

@pytest.mark.parametrize('failure',['timeout','length','json','usage'])
def test_errors_never_retry(configured,monkeypatch,failure):
    fake=Fake(failure);monkeypatch.setattr(live,'get_adapter',lambda:live.ManualAdapter(fake,limits=CollectionDraftLimits(max_output_tokens=4000)))
    with TestClient(app) as c:
        request=body();assert c.post('/api/companies/'+METAL+'/live-synthetic/analyses',json=request).status_code==502
        assert c.post('/api/companies/'+METAL+'/live-synthetic/analyses',json=request).status_code==409
    assert fake.calls==1


def test_no_auth_is_401_no_unknown_profile_no_extra_db_fields(configured):
    app.dependency_overrides.clear()
    with TestClient(app) as c:assert c.post('/api/companies/'+METAL+'/live-synthetic/analyses',json=body()).status_code==401
    with pytest.raises(HTTPException):live.profile('U_UNAPPROVED')
    dto=live.make_dto(METAL,live.ManualNews(**body()))
    adapter=live.ManualAdapter(Fake())
    with pytest.raises(ValueError):adapter.verify_dto(dto.model_copy(update={'messages':()}))
    with pytest.raises(ValueError):live.ManualNews(**body(),db_profile={'secret':'not-allowed'})



def test_live_flag_absent_is_disabled_even_with_test_key(configured,monkeypatch):
    monkeypatch.delenv('LIVE_SYNTHETIC_ANALYSIS_ENABLED',raising=False)
    assert live.enabled() is False
    with TestClient(app) as c:
        assert c.get('/api/companies/'+METAL+'/live-synthetic/status').json()['enabled'] is False
        assert c.post('/api/companies/'+METAL+'/live-synthetic/analyses',json=body()).status_code==503
