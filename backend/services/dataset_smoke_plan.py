"""Read-only preflight; no job, adapter construction, HTTP or SDK dispatch."""
from dataclasses import dataclass
from repositories.auth_repository import AuthRepository
from repositories.company_repository import CompanyRepository
from repositories.news_repository import NewsRepository
from services.auth_service import unauthorized, denied
from services.dataset_analysis import HackathonDatasetPolicy, sha
import json


@dataclass(frozen=True, repr=False)
class DatasetSmokePlan:
    dto: object
    input_byte_allowance: int
    source_count: int
    pair_sha256: str
    dto_sha256: str

    def summary(self):
        return {"status":"PLAN_ONLY","requests":0,"maximum_future_requests":1,
            "model":"deepseek/deepseek-v4.1-flash",
            "base_url":"https://changellenge.up.railway.app/v1",
            "input_byte_allowance":self.input_byte_allowance,"max_input_tokens":8000,
            "max_output_tokens_including_reasoning":2000,"sdk_timeout_seconds":60,
            "total_timeout_seconds":120,"retries":0,"fallback":False,
            "source_count":self.source_count,"dto_sha256":self.dto_sha256,
            "pair_sha256":self.pair_sha256,"cost":"UNKNOWN_NOT_A_MONETARY_GUARANTEE"}


async def prepare_smoke_plan(sessions,actor,source_id,news_id,manifest):
    policy=HackathonDatasetPolicy(manifest)
    async with sessions() as session:
        auth=AuthRepository(session)
        principal=await auth.principal(actor.token_hash)
        if principal is None:
            raise unauthorized()
        if (principal["id"]!=actor.user_id or not await auth.company_allowed(actor.user_id,source_id,True)
                or not await auth.news_allowed(actor.user_id,news_id)):
            raise denied()
        record=await CompanyRepository(session).get_by_source_id(source_id)
        news=await NewsRepository(session).get_by_id(news_id)
        if record is None or news is None:
            raise denied()
        context=await policy.load_context(session,record)
    dto,evidence=policy.prepare(context,news["content"])
    policy.verify(dto)
    allowance=len(json.dumps([m.model_dump() for m in dto.messages],ensure_ascii=False).encode())+512
    if allowance>8000:
        from services.external_context_policy import PolicyDenied
        raise PolicyDenied()
    return DatasetSmokePlan(dto,allowance,len(evidence),sha(source_id+"\n"+str(news_id)),policy.verify(dto))
