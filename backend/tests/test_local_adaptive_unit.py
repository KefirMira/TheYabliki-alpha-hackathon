import asyncio
import copy
from unittest.mock import AsyncMock
import pytest
from pydantic import ValidationError
from schemas.orchestration import Observation, OrchestrationTrace
from services.local_adaptive_service import LocalAdaptiveAgent, AgentStopped, fake_decision
from services.synthetic_news_execution_service import LocalFakeAnalysisSDK


def observation(**kwargs):
    return Observation(stage='evidence',missing_context=0,context_partial=False,source_count=2,**kwargs)


@pytest.mark.parametrize('partial,count,searched,action',[(False,2,False,'DRAFT'),
    (True,2,False,'SEARCH_RAG'),(False,1,False,'SEARCH_RAG'),(True,1,True,'DRAFT'),
    (False,0,False,'STOP')])
def test_planner_depends_on_observations(partial,count,searched,action):
    assert fake_decision(Observation(stage='evidence',missing_context=0,context_partial=partial,
        source_count=count,searched=searched)).action == action


@pytest.mark.parametrize('decision',[{'action':'SHELL','reason':'BLOCKER'},
    {'action':'DRAFT','reason':'EVIDENCE_READY','company_id':'other'},
    {'action':'KEEP_WITH_WARNINGS','reason':'REVIEW_REQUIRED'},
    {'action':'DRAFT','reason':'EVIDENCE_READY','field':'risks[0]'}])
def test_unknown_tools_and_wrong_phase_rejected(decision):
    sdk = LocalFakeAnalysisSDK()
    sdk.decide = AsyncMock(return_value=decision)
    agent = LocalAdaptiveAgent(sdk,OrchestrationTrace())
    with pytest.raises(AgentStopped):
        asyncio.run(agent.decide(observation()))


def test_decisions_and_journal_strictly_bounded():
    agent = LocalAdaptiveAgent(LocalFakeAnalysisSDK(),OrchestrationTrace())
    async def run():
        for _ in range(3):
            await agent.decide(observation())
        with pytest.raises(AgentStopped,match='DECISION_LIMIT'):
            await agent.decide(observation())
    asyncio.run(run())
    for _ in range(32-len(agent.trace.events)):
        agent.log('OBSERVE','LOCAL_OBSERVATION')
    with pytest.raises(AgentStopped,match='TRACE_LIMIT'):
        agent.log('OBSERVE','LOCAL_OBSERVATION')
    assert len(agent.trace.events)==32
    for invalid in ({'paid_calls':1},{'status':'COMPLETED'},{'secret':'value'}):
        with pytest.raises(ValidationError):
            OrchestrationTrace(**invalid)


@pytest.mark.parametrize('case',['empty','tamper','second_search'])
def test_sources_and_search_bounds(case,monkeypatch):
    sdk = LocalFakeAnalysisSDK()
    agent = LocalAdaptiveAgent(sdk,OrchestrationTrace())
    corpus = [{'source':'synthetic.pdf','page':1,'text':'Учебная ставка','chunk_id':1}]
    evidence = dict(id=1,document='synthetic.pdf',page=1,text='Учебная ставка',chunk_id=1,date=None,score=0.2)
    payload = {'company_source_assertions':{'facts':{},'missing':[]},
        'news_from_db':{'content':'Учебная ставка'},'analytical_source_assertions':[evidence]}
    if case=='empty': payload['analytical_source_assertions']=[]
    if case=='tamper': evidence['text']='Invented source'
    if case=='second_search':
        sdk.decide=AsyncMock(return_value={'action':'SEARCH_RAG','reason':'CONTEXT_GAPS'})
    with pytest.raises(AgentStopped):
        asyncio.run(agent.select_evidence(copy.deepcopy(payload),corpus))
    assert agent.trace.drafts==0 and agent.trace.searches<=1


def test_supplementary_retrieval_adds_only_frozen_source_and_replans(monkeypatch):
    from services import local_adaptive_service as module
    corpus=[dict(source='synthetic-a.pdf',page=1,chunk_id=1,text='Учебная ставка'),
            dict(source='synthetic-b.pdf',page=2,chunk_id=2,text='Учебный отраслевой контекст')]
    first=dict(id=1,document='synthetic-a.pdf',page=1,chunk_id=1,text='Учебная ставка',date=None,score=0.4)
    payload={'company_source_assertions':{'facts':{},'missing':['industry']},
        'news_from_db':{'content':'Учебная ставка'},'analytical_source_assertions':[first]}
    monkeypatch.setattr(module,'search_chunks',lambda *args,**kwargs:[dict(corpus[1],score=0.2)])
    agent=LocalAdaptiveAgent(LocalFakeAnalysisSDK(),OrchestrationTrace())
    asyncio.run(agent.select_evidence(payload,corpus))
    assert len(payload['analytical_source_assertions'])==2
    assert agent.trace.searches==1 and agent.trace.decisions==2
    decisions=[e for e in agent.trace.events if e.tool=='DECIDE']
    assert [e.decision.action for e in decisions]==['SEARCH_RAG','DRAFT']
    assert decisions[0].remaining_plan != decisions[1].remaining_plan
    assert all(e.observation.source_support=='UNKNOWN' for e in agent.trace.events if e.observation)


def test_planner_cannot_authorize_draft_without_sources():
    sdk=LocalFakeAnalysisSDK()
    sdk.decide=AsyncMock(return_value={'action':'DRAFT','reason':'EVIDENCE_READY'})
    agent=LocalAdaptiveAgent(sdk,OrchestrationTrace())
    payload={'company_source_assertions':{'facts':{},'missing':[]},
             'news_from_db':{'content':'Synthetic'},'analytical_source_assertions':[]}
    with pytest.raises(AgentStopped,match='NO_SOURCES'):
        asyncio.run(agent.select_evidence(payload,[]))
