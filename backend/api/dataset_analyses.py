"""Opt-in dataset path; original company guard and legacy endpoints remain blocked."""
import asyncio
import os
import hashlib
import re
from typing import Literal
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Path, Response
from sqlalchemy import text
from repositories.company_repository import CompanyRepository
from pydantic import BaseModel, ConfigDict
from api.auth import company_write, AUTH_ERRORS
from api.company_analyses import _created_analysis
from db.session import get_session_factory
from schemas.company_analysis_api import CreatedCompanyAnalysis
from schemas.http_docs import ANALYSIS_ERRORS, APIError
from services.company_analysis_service import CompanyAnalysisService
from services.external_context_policy import PolicyDenied

router = APIRouter(prefix="/api/companies", tags=["hackathon dataset analysis"], responses=AUTH_ERRORS)


class CandidateNews(BaseModel):
    id: int
    title: str
    content: str
    published_at: datetime | None


class CandidateNewsResponse(BaseModel):
    matching: Literal["TOPICAL_CANDIDATES_NOT_CONFIRMED"]
    items: list[CandidateNews]


class DatasetConsent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    news_external_transfer_confirmed: Literal[True]


def dataset_mode():
    value = os.environ.get("DATASET_AI_TRANSPORT", "off")
    if value not in {"off","fake","organizer"}:
        return "off"
    return value


def dataset_enabled():
    mode = dataset_mode()
    if mode == "off":
        return False
    if mode == "organizer" and (os.environ.get("DATASET_AI_REAL_CONFIRMED") != "one-bounded-draft-approved"
            or not re.fullmatch(r"[a-f0-9]{64}", os.environ.get("DATASET_AI_REAL_PAIR_SHA256",""))):
        return False
    return bool(os.environ.get("DATASET_AI_MANIFEST") and os.environ.get("DATASET_AI_MANIFEST_SHA256"))


@router.post("/{source_id}/news/{news_id}/dataset-analyses", response_model=CreatedCompanyAnalysis,
    status_code=201, responses={**ANALYSIS_ERRORS,200:{"model":CreatedCompanyAnalysis,
        "description":"COMPLETED cache после ACL, без нового вызова"},
        403:{"model":APIError,"description":"ACL/новость/право записи запрещены"},
        503:{"model":APIError,"description":"DATASET_PATH_DISABLED / DATASET_POLICY_DENIED"}},
    description="Отдельный opt-in путь датасета. Нужны can_analyze, news grant и подтверждение права передачи текста новости. "
        "CSV snapshot и совокупный DTO проверяются manifest-политикой. Общий guard неизменен. "
        "Одна попытка SDK, без retries/fallback, максимум 2000 output включая reasoning, timeout 60/120 секунд. "
        "Существующие jobs/cache/FAILED/admin retry; UNKNOWN не разрешает автоматический повтор.")
async def dataset_analysis(body: DatasetConsent, response: Response,
    source_id: str = Path(min_length=1,max_length=200),
    news_id: int = Path(gt=0,le=9223372036854775807),
    actor=Depends(company_write), sessions=Depends(get_session_factory)):
    if not dataset_enabled():
        raise HTTPException(503,detail={"code":"DATASET_PATH_DISABLED","message":"Разрешённый dataset-путь выключен."})
    if dataset_mode()=="organizer":
        pair_hash=hashlib.sha256((source_id+"\n"+str(news_id)).encode()).hexdigest()
        if pair_hash != os.environ.get("DATASET_AI_REAL_PAIR_SHA256"):
            raise HTTPException(503,detail={"code":"DATASET_REAL_PAIR_NOT_APPROVED",
                "message":"Для первого реального smoke разрешена только одна явно выбранная пара."})
    from services.dataset_analysis import (
        load_manifest, DatasetAnalyzer, DatasetDraftAdapter, LocalDatasetClient, DraftLimits, DraftStopped)
    adapter = None
    try:
        manifest = load_manifest()
        limits = DraftLimits(max_input_tokens=8000,max_output_tokens=2000)
        # Keep existing strict input allowance (UTF-8 bytes + 512), not a money guarantee.
        if dataset_mode()=="fake":
            adapter = DatasetDraftAdapter(LocalDatasetClient(),limits=limits)
        else:
            adapter = DatasetDraftAdapter.organizer(api_key=os.environ.get("LLM_API_KEY",""),
                allow_real=True,acknowledge_unknown_cost=True,limits=limits)
        analyzer = DatasetAnalyzer(sessions,actor,manifest,adapter,news_id)
        service = CompanyAnalysisService(sessions,analyzer=analyzer,
            context_loader=analyzer.policy.load_context,actor_id=actor.user_id)
        async with asyncio.timeout(120):
            return await _created_analysis(source_id,service.analyze_saved(source_id,news_id),response)
    except DraftStopped:
        raise HTTPException(503,detail={"code":"DATASET_GATEWAY_NOT_READY","message":"Gateway не подготовлен; запрос не отправлен."}) from None
    except PolicyDenied:
        raise HTTPException(503,detail={"code":"DATASET_POLICY_DENIED",
            "message":"Контекст, источник или разрешение не прошли проверку."}) from None
    except TimeoutError:
        raise HTTPException(503,detail={"code":"DATASET_OUTCOME_UNKNOWN",
            "message":"Исход не подтверждён. Не повторяйте запрос; требуется проверка задания."}) from None
    finally:
        if adapter is not None:
            try:
                await adapter.aclose()
            except Exception:
                # Never turn an already committed result into a client-visible retry invitation.
                pass



@router.get("/{source_id}/dataset-news", response_model=CandidateNewsResponse, description="До пяти тематических кандидатов из последних 50 новостей с news grant. "
    "Без внешних запросов, matching не подтверждён; не назначает grant и не запускает jobs.")
async def dataset_news(source_id: str = Path(min_length=1,max_length=200),
    actor=Depends(company_write), sessions=Depends(get_session_factory)):
    if not dataset_enabled():
        raise HTTPException(503,detail={"code":"DATASET_PATH_DISABLED","message":"Dataset-путь выключен."})
    from services.dataset_analysis import HackathonDatasetPolicy, load_manifest
    from services.search_service import search_chunks
    try:
        policy=HackathonDatasetPolicy(load_manifest())
        async with sessions() as session:
            record=await CompanyRepository(session).get_by_source_id(source_id)
            if record is None:
                raise PolicyDenied()
            context=await policy.load_context(session,record)
            rows=(await session.execute(text("""
                SELECT n.id,n.title,n.content,n.published_at FROM news_articles n
                JOIN auth_news_grants g ON g.news_id=n.id AND g.user_id=:actor
                WHERE n.content IS NOT NULL AND octet_length(n.content)<=5000
                ORDER BY n.id DESC LIMIT 50
            """),{"actor":actor.user_id})).mappings().all()
        query=context["facts"].get("industry",{}).get("value","")
        ranked=search_chunks(query,[dict(source=str(row["id"]),page=1,chunk_id=1,text=row["content"])
            for row in rows],top_k=5) if query else []
        by_id={str(row["id"]):row for row in rows}
        return {"matching":"TOPICAL_CANDIDATES_NOT_CONFIRMED","items":[dict(by_id[c["source"]]) for c in ranked]}
    except PolicyDenied:
        raise HTTPException(503,detail={"code":"DATASET_POLICY_DENIED","message":"Не подтверждён dataset snapshot."}) from None
