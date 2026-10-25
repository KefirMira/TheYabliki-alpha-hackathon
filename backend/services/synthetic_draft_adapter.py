"""One bounded OpenAI-compatible draft. No env loading, retries, fallback or DB input."""
import asyncio
import json
import time
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from schemas.analysis import AnalysisContent
from services.synthetic_gateway_input import verify_input
from services.synthetic_news_execution_service import LocalExecutionStopped

BASE_URL = 'https://changellenge.up.railway.app/v1'
MODEL = 'deepseek/deepseek-v4.1-flash'


class DraftLimits(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)
    max_requests: Literal[1] = 1
    max_input_tokens: int = Field(default=8000, ge=1, le=8000)
    max_output_tokens: int = Field(default=1000, ge=1, le=2000)
    request_seconds: int = Field(default=60, ge=1, le=60)

    @field_validator('max_requests',mode='before')
    @classmethod
    def integer_request_count(cls,value):
        if type(value) is not int:
            raise ValueError('INTEGER_REQUEST_COUNT_REQUIRED')
        return value


class DraftStopped(LocalExecutionStopped):
    pass


def field(value, key, default=None):
    return value.get(key, default) if isinstance(value,dict) else getattr(value,key,default)


def strict_object(pairs):
    result={}
    for k,v in pairs:
        if k in result:
            raise ValueError('DUPLICATE_JSON_FIELD')
        result[k]=v
    return result


class SyntheticDraftAdapter:
    """Injected clients are local test doubles. Real client creation is explicit and opt-in only."""
    def __init__(self, fake_client, *, limits=None):
        self._client = fake_client
        self.limits = DraftLimits.model_validate((limits or DraftLimits()).model_dump())
        self.transport = 'fake'
        self.requests = 0
        self.usage = None
        self.finish_reason = None
        self.outcome = 'NOT_SENT'
        self.outbound_sha256 = None
        self.elapsed_ms = 0
        self._authorized = False

    @classmethod
    def organizer(cls, *, api_key, allow_real=False, acknowledge_unknown_cost=False,
                  base_url=BASE_URL, model=MODEL, limits=None):
        # Deliberately never called by API routing or by automatic configuration discovery.
        if (allow_real is not True or acknowledge_unknown_cost is not True
                or base_url!=BASE_URL or model!=MODEL or not isinstance(api_key,str) or not api_key.strip()):
            raise DraftStopped('GATEWAY_EXPLICIT_AUTHORIZATION_REQUIRED')
        from settings import ai_disabled_reason
        if ai_disabled_reason():
            raise DraftStopped('AI_DISABLED_IN_DEMO')
        selected_limits=DraftLimits.model_validate((limits or DraftLimits()).model_dump())
        from openai import AsyncOpenAI, DefaultAsyncHttpxClient
        result=cls(AsyncOpenAI(api_key=api_key,base_url=BASE_URL,max_retries=0,
            timeout=selected_limits.request_seconds,
            http_client=DefaultAsyncHttpxClient(follow_redirects=False,trust_env=False)),limits=selected_limits)
        result.transport='organizer'
        result._authorized=True
        return result

    async def aclose(self):
        await self._client.close()

    async def complete(self, dto):
        if self.transport=='organizer':
            from settings import ai_disabled_reason
            if not self._authorized:
                raise DraftStopped('GATEWAY_EXPLICIT_AUTHORIZATION_REQUIRED')
            if ai_disabled_reason():
                raise DraftStopped('AI_DISABLED_IN_DEMO')
        try:
            self.outbound_sha256=verify_input(dto)
        except (ValueError,TypeError,AttributeError):
            raise DraftStopped('SYNTHETIC_INPUT_PROVENANCE_FAILED') from None
        # UTF-8 bytes are a conservative planning allowance, not a verified model tokenizer.
        messages=[m.model_dump() for m in dto.messages]
        byte_bound=len(json.dumps(messages,ensure_ascii=False).encode())+512
        if byte_bound>self.limits.max_input_tokens:
            raise DraftStopped('GATEWAY_INPUT_LIMIT')
        if self.requests:
            raise DraftStopped('GATEWAY_REQUEST_LIMIT')
        # No await before reservation: a shared adapter cannot dispatch twice under asyncio.
        self.requests=1
        self.outcome='UNKNOWN'
        started=time.monotonic()
        try:
            async with asyncio.timeout(self.limits.request_seconds):
                # Recheck trusted bytes at the last boundary; never forward an original caller object.
                verify_input(dto)
                response=await self._client.with_options(max_retries=0,timeout=self.limits.request_seconds).chat.completions.create(
                    model=MODEL,messages=messages,max_tokens=self.limits.max_output_tokens)
            choices=field(response,'choices')
            if not choices or len(choices)!=1:
                raise DraftStopped('GATEWAY_RESPONSE_INVALID')
            choice=choices[0]
            finish=field(choice,'finish_reason')
            self.finish_reason=finish if finish in {'stop','length'} else 'other'
            usage=field(response,'usage')
            values={k:field(usage,k) for k in ('prompt_tokens','completion_tokens','total_tokens')}
            if any(type(v) is not int or v<0 for v in values.values()):
                raise DraftStopped('GATEWAY_USAGE_UNKNOWN')
            details=field(usage,'completion_tokens_details')
            reasoning=field(details,'reasoning_tokens')
            if reasoning is not None:
                if type(reasoning) is not int or not 0<=reasoning<=values['completion_tokens']:
                    raise DraftStopped('GATEWAY_USAGE_UNKNOWN')
                values['reasoning_tokens']=reasoning
            self.usage=values
            if (values['prompt_tokens']>self.limits.max_input_tokens
                    or values['completion_tokens']>self.limits.max_output_tokens
                    or values['total_tokens']!=values['prompt_tokens']+values['completion_tokens']):
                raise DraftStopped('GATEWAY_USAGE_LIMIT')
            if finish!='stop':
                raise DraftStopped('GATEWAY_RESPONSE_INCOMPLETE')
            message=field(choice,'message')
            raw=field(message,'content')
            if field(message,'tool_calls') or field(message,'function_call'):
                raise DraftStopped('GATEWAY_TOOL_CALL_FORBIDDEN')
            if not isinstance(raw,str) or not raw.strip() or len(raw.encode())>32000:
                raise DraftStopped('GATEWAY_RESPONSE_EMPTY_OR_LARGE')
            data=json.loads(raw,object_pairs_hook=strict_object,parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if not isinstance(data,dict) or set(data)!=set(AnalysisContent.model_fields):
                raise ValueError('SCHEMA_FIELDS')
            AnalysisContent.model_validate(data,strict=True)
            self.outcome='RESPONSE_VALIDATED'
            return raw
        except DraftStopped:
            raise
        except asyncio.TimeoutError:
            raise DraftStopped('GATEWAY_TIMEOUT_UNKNOWN') from None
        except (ValueError,TypeError):
            raise DraftStopped('GATEWAY_JSON_INVALID') from None
        except asyncio.CancelledError:
            raise
        except Exception as error:
            code='GATEWAY_QUOTA_EXCEEDED' if 'budget has been exceeded' in str(error).casefold() else 'GATEWAY_REQUEST_UNKNOWN'
            raise DraftStopped(code) from None
        finally:
            self.elapsed_ms=max(0,int((time.monotonic()-started)*1000))
