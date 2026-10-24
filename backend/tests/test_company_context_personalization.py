import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from schemas.company import CompanyProfile
from services.company_context_service import build_context, CompanyContextExternalTransferBlocked
from services.personalization_service import analyze_for_company
from test_company_context_unit import row


def test_company_context_prompt_differences_and_exact_decimal():
    questions=[]
    async def local_rag(**kwargs):
        questions.append(kwargs['question'])
        return {'analysis':json.dumps({'relevance':'unknown','summary':'Недостаточно данных; отраслевое влияние — предположение.',
            'risks':[],'opportunities':[],'recommendations':[]}),
            'sources':[{'id':1,'document':'synthetic.pdf','page':1,'score':0.1}]}
    async def scenario():
        for industry,flag in [('Синтетическое производство','1'),('Синтетическая розница','0')]:
            company=CompanyProfile(company_id='PRIVATE-ID-NOT-FOR-PROMPT')
            company._ai_context=build_context(row(industry=industry,csv_fields={'CL_PRODUCT_LOA_MARK':flag}))
            result=await analyze_for_company('Одинаковая синтетическая новость',company,_local_rag=local_rag)
            assert result['relevance']=='unknown' and result['risks']==[]
            assert 'PRIVATE-ID-NOT-FOR-PROMPT' not in questions[-1]
            assert '1234567890.12' in questions[-1]
            assert 'не доказывает долг' in questions[-1]
            assert 'отраслевую' in questions[-1].lower()
            assert 'PAY_AMT' not in questions[-1]
        assert questions[0]!=questions[1]
    asyncio.run(scenario())


def test_company_context_never_reaches_external_gateway(monkeypatch):
    import services.personalization_service as module
    gateway=AsyncMock(side_effect=AssertionError('No external calls'))
    monkeypatch.setattr(module,'analyze_with_rag',gateway)
    company=CompanyProfile(company_id='Synthetic')
    company._ai_context=build_context(row())
    with pytest.raises(CompanyContextExternalTransferBlocked):
        asyncio.run(analyze_for_company('Synthetic',company))
    gateway.assert_not_called()


def test_company_context_private_attribute_preserves_wire_schema():
    company=CompanyProfile.model_validate({'company_id':'Synthetic','_ai_context':{'injected':True}})
    assert company._ai_context is None
    before=company.model_dump()
    company._ai_context=build_context(row())
    assert company.model_dump()==before
    assert '_ai_context' not in CompanyProfile.model_json_schema()['properties']


def test_company_context_http_privacy_error():
    from fastapi import HTTPException
    from api.company_analyses import _created_analysis
    async def blocked():
        raise CompanyContextExternalTransferBlocked()
    with pytest.raises(HTTPException) as error:
        asyncio.run(_created_analysis('Synthetic',blocked()))
    assert error.value.status_code==503
    assert error.value.detail=={'code':'COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED',
                               'message':'Передача контекста БД внешнему AI не разрешена.'}


@pytest.mark.parametrize('path,payload',[
    ('/api/companies/Synthetic/analyses',{'news':{'text':'Synthetic news'}}),
    ('/api/companies/Synthetic/news/1/analyses',None),
])
def test_company_context_api_privacy_response(monkeypatch,path,payload):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from api.company_analyses import get_analysis_service
    from main import app
    monkeypatch.delenv('DATABASE_URL',raising=False)
    monkeypatch.setenv('AI_MODE','full')
    service=SimpleNamespace(analyze=AsyncMock(side_effect=CompanyContextExternalTransferBlocked()),
                            analyze_saved=AsyncMock(side_effect=CompanyContextExternalTransferBlocked()))
    app.dependency_overrides[get_analysis_service]=lambda:service
    try:
        with TestClient(app) as client:
            response=client.post(path,json=payload)
            assert response.status_code==503
            assert response.json()['detail']['code']=='COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED'
            schema=client.get('/openapi.json').json()
            assert '_ai_context' not in json.dumps(schema)
    finally:app.dependency_overrides.clear()
