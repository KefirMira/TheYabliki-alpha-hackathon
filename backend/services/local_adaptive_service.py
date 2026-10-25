"""Bounded local decisions, existing retrieval and conservative removal. No network."""
import copy
import json
import re
from schemas.orchestration import Decision, Observation, OrchestrationTrace, TraceEvent
from schemas.persisted_analysis import PersistableAnalysis, RetrievedEvidence
from services.analysis_preparation_service import digest, MAX_INPUT_BYTES
from services.search_service import search_chunks

CORRECTABLE = {'FINANCIAL_NUMBER_NOT_IN_INPUT', 'COMPANY_CONTRACT_NUMBER_UNVERIFIED',
    'UNSUPPORTED_UNCHANGED_BORROWING_COST', 'COMPANY_FACT_NOT_ESTABLISHED',
    'COMPANY_PROJECTION_AS_FACT', 'STRUCTURAL_COUNT_AS_FINANCIAL_INFERENCE'}
ITEM = re.compile(r'^(risks|opportunities|recommendations)\[(\d+)\]$')


class AgentStopped(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def fake_decision(observation):
    if not observation.source_count:
        return Decision(action='STOP', reason='NO_SOURCES')
    if observation.stage == 'evidence':
        if not observation.searched and (observation.context_partial or observation.source_count < 2):
            return Decision(action='SEARCH_RAG', reason='CONTEXT_GAPS' if observation.context_partial else 'SINGLE_SOURCE')
        return Decision(action='DRAFT', reason='EVIDENCE_READY')
    if observation.blocker:
        return Decision(action='STOP', reason='BLOCKER')
    if observation.correctable_fields:
        return Decision(action='REMOVE_CLAIM', reason='UNSUPPORTED_ITEM', field=observation.correctable_fields[0])
    return Decision(action='KEEP_WITH_WARNINGS', reason='REVIEW_REQUIRED')


class LocalAdaptiveAgent:
    def __init__(self, sdk, trace):
        self.sdk, self.trace = sdk, trace
        self.last_review = None

    def log(self, tool, reason, **kwargs):
        candidate = self.trace.model_copy(deep=True)
        candidate.events.append(TraceEvent(tool=tool, reason=reason, **kwargs))
        try:
            candidate.checked()
        except ValueError as error:
            raise AgentStopped('AGENT_TRACE_LIMIT') from error
        self.trace.events = candidate.events

    def observe(self, payload, review=None):
        facts = payload['company_source_assertions']['facts']
        unresolved = set() if review is None else {f.field for f in review.findings if f.code=='CLAIM_SCOPE_UNRESOLVED'}
        fields = [] if review is None else list(dict.fromkeys(f.field for f in review.findings
            if f.disposition == 'NEEDS_REVIEW' and f.code in CORRECTABLE and ITEM.fullmatch(f.field)
            and f.field not in unresolved))[:16]
        return Observation(stage='review' if review else 'evidence',
            missing_context=len(payload['company_source_assertions']['missing']),
            context_partial=not any(key in facts for key in ('industry','okved_code')),
            source_count=len(payload['analytical_source_assertions']), searched=bool(self.trace.searches),
            blocker=bool(review and review.blocking),
            finding_codes=[] if review is None else list(dict.fromkeys(f.code for f in review.findings))[:16],
            correctable_fields=fields)

    async def decide(self, observation):
        if self.trace.decisions >= 3:
            raise AgentStopped('AGENT_DECISION_LIMIT')
        self.trace.decisions += 1
        self.log('OBSERVE', 'LOCAL_OBSERVATION', observation=observation)
        try:
            decision = Decision.model_validate(await self.sdk.decide(observation.model_copy(deep=True)))
        except ValueError as error:
            raise AgentStopped('AGENT_INVALID_DECISION') from error
        allowed = {'DRAFT','SEARCH_RAG','STOP'} if observation.stage == 'evidence' else {'REMOVE_CLAIM','KEEP_WITH_WARNINGS','STOP'}
        if (decision.action not in allowed or
                (decision.action == 'REMOVE_CLAIM' and decision.field not in observation.correctable_fields) or
                (decision.action != 'REMOVE_CLAIM' and decision.field is not None)):
            raise AgentStopped('AGENT_ACTION_NOT_ALLOWED')
        plans = {'SEARCH_RAG':['SEARCH_RAG','DECIDE','DRAFT','VALIDATE','REVIEW','DECIDE','PERSIST'],
                 'DRAFT':['DRAFT','VALIDATE','REVIEW','DECIDE','PERSIST'],
                 'REMOVE_CLAIM':['REMOVE_CLAIM','VALIDATE','REVIEW','PERSIST'],
                 'KEEP_WITH_WARNINGS':['PERSIST'], 'STOP':['STOP']}
        self.log('DECIDE', decision.reason, decision=decision, remaining_plan=plans[decision.action])
        return decision

    def ensure_corpus(self, evidence, corpus):
        allowed = {(c['source'],c['page'],c.get('chunk_id',1),c.get('date'),c['text']) for c in corpus}
        if any((e['document'],e['page'],e['chunk_id'],e.get('date'),e['text']) not in allowed for e in evidence):
            raise AgentStopped('AGENT_SOURCE_PROVENANCE_MISMATCH')

    async def select_evidence(self, payload, corpus):
        self.ensure_corpus(payload['analytical_source_assertions'], corpus)
        while True:
            observation = self.observe(payload)
            decision = await self.decide(observation)
            if not observation.source_count or decision.action == 'STOP':
                raise AgentStopped('AGENT_NO_SOURCES')
            if decision.action == 'DRAFT':
                return
            if self.trace.searches:
                raise AgentStopped('AGENT_SEARCH_LIMIT')
            self.trace.searches += 1
            facts = payload['company_source_assertions']['facts']
            industry = facts.get('industry',{}).get('value','')
            query = (str(industry) + ' ' + payload['news_from_db']['content'])[:2000]
            selected = search_chunks(query, copy.deepcopy(corpus), top_k=3)
            evidence = payload['analytical_source_assertions']
            for chunk in selected:
                if not any((e['document'],e['page'],e['chunk_id'],e.get('date'),e['text']) ==
                           (chunk['source'],chunk['page'],chunk.get('chunk_id',1),chunk.get('date'),chunk['text']) for e in evidence):
                    evidence.append(RetrievedEvidence(id=len(evidence)+1,document=chunk['source'],page=chunk['page'],
                        chunk_id=chunk.get('chunk_id',1),date=chunk.get('date'),score=chunk['score'],text=chunk['text']).model_dump())
            if len(evidence)>6 or len(json.dumps(payload,ensure_ascii=False,default=str).encode())>MAX_INPUT_BYTES:
                raise AgentStopped('AGENT_INPUT_LIMIT')
            self.ensure_corpus(evidence, corpus)
            self.log('SEARCH_RAG', 'LOCAL_SEARCH_COMPLETED', before_sha256=digest(query),
                     after_sha256=digest(evidence), source_ids=[e['id'] for e in evidence])

    def verify(self, bundle, payload, company_id):
        bundle = PersistableAnalysis.model_validate(bundle.model_dump())
        if ([e.model_dump() for e in bundle.evidence] != payload['analytical_source_assertions']
                or bundle.analysis.news != payload['news_from_db']['content']
                or bundle.analysis.company_id != company_id):
            raise AgentStopped('AGENT_RESULT_PROVENANCE_MISMATCH')
        self.log('VALIDATE', 'SCHEMA_AND_EXACT_PROVENANCE', after_sha256=digest(bundle.model_dump(mode='json')))
        return bundle

    def review(self, bundle, payload, reviewer):
        if self.trace.reviews >= 2:
            raise AgentStopped('AGENT_REVIEW_LIMIT')
        self.trace.reviews += 1
        review = reviewer(bundle.analysis,payload['company_source_assertions'],payload['analytical_source_assertions'],payload['news_from_db']['content'])
        self.last_review = review
        self.log('REVIEW', 'FINANCIAL_CORRECTNESS_UNKNOWN', observation=self.observe(payload,review),
                 after_sha256=digest(review.model_dump(mode='json')))
        return review

    async def check_and_correct(self, bundle, raw, payload, reviewer, reassemble):
        company_id = bundle.analysis.company_id
        bundle = self.verify(bundle,payload,company_id)
        review = self.review(bundle,payload,reviewer)
        decision = await self.decide(self.observe(payload,review))
        if review.blocking or decision.action == 'STOP':
            raise AgentStopped('FINANCIAL_REVIEW_BLOCKED')
        if decision.action == 'REMOVE_CLAIM':
            if self.trace.corrections:
                raise AgentStopped('AGENT_CORRECTION_LIMIT')
            self.trace.corrections += 1
            data = json.loads(raw)
            key,index = ITEM.fullmatch(decision.field).groups()
            before = digest(data)
            del data[key][int(index)]
            self.log('REMOVE_CLAIM','WHOLE_ITEM_REMOVED',field=decision.field,
                     before_sha256=before,after_sha256=digest(data))
            bundle = self.verify(await reassemble(json.dumps(data,ensure_ascii=False)),payload,company_id)
            review = self.review(bundle,payload,reviewer)
            if review.blocking:
                raise AgentStopped('FINANCIAL_REVIEW_BLOCKED')
        self.log('KEEP_WITH_WARNINGS','HUMAN_REVIEW_REQUIRED')
        self.trace.status = 'VALIDATED'
        self.trace.checked()
        return bundle, review
