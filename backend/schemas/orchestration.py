"""Bounded audit contract for the local synthetic agent; never a truth certificate."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Action = Literal['DRAFT', 'SEARCH_RAG', 'KEEP_WITH_WARNINGS', 'REMOVE_CLAIM', 'STOP']
Tool = Literal['PREPARE', 'OBSERVE', 'DECIDE', 'SEARCH_RAG', 'DRAFT', 'VALIDATE',
               'REVIEW', 'REMOVE_CLAIM', 'KEEP_WITH_WARNINGS', 'STOP', 'PERSIST']


class Observation(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    stage: Literal['evidence', 'review']
    missing_context: int = Field(ge=0)
    context_partial: bool
    source_count: int = Field(ge=0, le=6)
    source_support: Literal['UNKNOWN'] = 'UNKNOWN'
    searched: bool = False
    blocker: bool = False
    finding_codes: list[str] = Field(default_factory=list, max_length=16)
    correctable_fields: list[str] = Field(default_factory=list, max_length=16)


class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    action: Action
    reason: Literal['NO_SOURCES', 'CONTEXT_GAPS', 'SINGLE_SOURCE', 'EVIDENCE_READY',
                    'BLOCKER', 'UNSUPPORTED_ITEM', 'REVIEW_REQUIRED']
    field: str | None = Field(default=None, pattern=r'^(risks|opportunities|recommendations)\[\d+\]$')


class TraceEvent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tool: Tool
    reason: str = Field(pattern=r'^[A-Z_]+$', max_length=80)
    observation: Observation | None = None
    decision: Decision | None = None
    remaining_plan: list[Tool] = Field(default_factory=list, max_length=8)
    source_ids: list[int] = Field(default_factory=list, max_length=6)
    before_sha256: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    after_sha256: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    field: str | None = Field(default=None, pattern=r'^(risks|opportunities|recommendations)\[\d+\]$')


class OrchestrationTrace(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: Literal['local-adaptive-v1'] = 'local-adaptive-v1'
    initial_plan: list[Tool] = Field(default_factory=lambda: ['PREPARE','DECIDE','DRAFT','VALIDATE','REVIEW','DECIDE','PERSIST'], max_length=8)
    status: Literal['RUNNING', 'VALIDATED', 'COMPLETED', 'FAILED'] = 'RUNNING'
    events: list[TraceEvent] = Field(default_factory=list, max_length=32)
    decisions: int = Field(default=0, ge=0, le=3)
    drafts: int = Field(default=0, ge=0, le=1)
    searches: int = Field(default=0, ge=0, le=1)
    corrections: int = Field(default=0, ge=0, le=1)
    reviews: int = Field(default=0, ge=0, le=2)
    paid_calls: Literal[0] = 0
    financial_correctness: Literal['UNKNOWN'] = 'UNKNOWN'
    human_review_required: Literal[True] = True

    @model_validator(mode='after')
    def bounds(self):
        if len(self.model_dump_json().encode('utf-8')) > 16384:
            raise ValueError('TRACE_TOO_LARGE')
        if self.status in {'VALIDATED','COMPLETED'} and (self.drafts != 1 or self.reviews < 1 or self.decisions < 2):
            raise ValueError('INCOMPLETE_TRACE')
        return self

    def checked(self):
        return type(self).model_validate(self.model_dump())

    def committed(self):
        if self.status != 'VALIDATED':
            raise ValueError('TRACE_NOT_VALIDATED')
        result = self.model_copy(deep=True)
        result.status = 'COMPLETED'
        result.events.append(TraceEvent(tool='PERSIST', reason='ATOMIC_COMMIT'))
        return result.checked()


class GatewayOrchestrationTrace(OrchestrationTrace):
    """Separate accounting contract; the original local trace remains paid_calls=0."""
    version: Literal['synthetic-gateway-v1'] = 'synthetic-gateway-v1'
    transport: Literal['fake', 'organizer'] = 'fake'
    sdk_requests: int = Field(default=0, ge=0, le=1)
    paid_calls: int = Field(default=0, ge=0, le=1)
    outbound_sha256: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    usage: dict[Literal['prompt_tokens','completion_tokens','total_tokens','reasoning_tokens'], int] | None = None
    finish_reason: Literal['stop','length','other'] | None = None
    request_outcome: Literal['NOT_SENT','UNKNOWN','RESPONSE_VALIDATED'] = 'NOT_SENT'
    elapsed_ms: int = Field(default=0, ge=0)
    error_code: str | None = Field(default=None,pattern=r'^[A-Z_]+$',max_length=80)

    @model_validator(mode='after')
    def accounting(self):
        if self.paid_calls != (self.sdk_requests if self.transport == 'organizer' else 0):
            raise ValueError('INVALID_DISPATCH_ACCOUNTING')
        if self.usage and any(isinstance(v,bool) or v<0 for v in self.usage.values()):
            raise ValueError('INVALID_USAGE')
        return self



class DatasetOrchestrationTrace(GatewayOrchestrationTrace):
    """Dataset permission is distinct from the frozen synthetic fixture contract."""
    version: Literal['hackathon-dataset-v1'] = 'hackathon-dataset-v1'
