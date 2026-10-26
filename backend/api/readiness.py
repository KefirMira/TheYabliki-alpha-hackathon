"""Readiness is local/configuration validation, never a paid provider probe."""
import asyncio
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from services.knowledge_base_service import load_knowledge_base
from settings import execution_mode, saved_pilot_offline
from db.diagnostics import database_error_code
from db.readiness import news_identity_ready
from schemas.http_docs import ReadinessResponse
from db.job_schema import JOB_SCHEMA_SQL, JOB_SCHEMA_SIGNATURE
from db.matching_schema import MATCH_SCHEMA_SQL, MATCH_SCHEMA_SIGNATURE

router = APIRouter()
TABLES = (
    "companies", "persons", "company_person_links", "company_payments",
    "news_articles", "analysis_runs", "company_news_analyses", "insight_evidence",
    "information_sources", "company_contexts", "company_documents",
    "company_insight_states", "insight_updates",
    "news_analysis_jobs", "news_analysis_attempts",
    "company_verified_names", "news_company_match_runs", "news_company_match_candidates",
    "auth_users", "auth_sessions", "auth_user_companies", "auth_news_grants",
)


def rag_ready() -> bool:
    try:
        chunks = load_knowledge_base()
        return bool(chunks) and all(
            isinstance(c.get("text"), str) and bool(c["text"].strip())
            and isinstance(c.get("source"), str) and bool(c["source"])
            and isinstance(c.get("page"), int) and c["page"] > 0
            for c in chunks
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


@router.get("/ready", responses={200: {"model": ReadinessResponse},
    503: {"model": ReadinessResponse, "description": "Компоненты не готовы; без DDL и обращения к LLM"}},
    description="22 таблиц; проверенные определения объектов 004–006. В demo требуется только БД; в full также RAG и конфигурация LLM (без запроса провайдеру).")
async def readiness(request: Request):
    offline = saved_pilot_offline()
    database_code = "DATABASE_NOT_CONFIGURED"
    checks = {
        "rag": False if offline else await asyncio.to_thread(rag_ready),
        "llm_config": all(os.environ.get(k, "").strip() for k in
                          ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")),
        "database": False,
    }
    sessions = getattr(request.app.state, "company_sessions", None)
    if sessions is not None:
        database_code = "DATABASE_UNAVAILABLE"
        try:
            async with asyncio.timeout(6):
                async with sessions() as session:
                    for table in TABLES:
                        result = await session.execute(
                            text("SELECT to_regclass(:name)"), {"name": f"public.{table}"}
                        )
                        if result.scalar_one() is None:
                            database_code = "DATABASE_TABLE_MISSING"
                            break
                    else:
                        database_code = "DATABASE_IDENTITY_SCHEMA_MISMATCH"
                        checks["database"] = await news_identity_ready(session)
                        if checks['database']:
                            database_code = 'DATABASE_JOB_SCHEMA_MISMATCH'
                            result = await session.execute(text('SELECT (:signature = (' + JOB_SCHEMA_SQL + '))'),
                                {'signature':JOB_SCHEMA_SIGNATURE})
                            checks['database'] = result.scalar_one() is True
                        if checks['database']:
                            database_code = 'DATABASE_MATCH_SCHEMA_MISMATCH'
                            result = await session.execute(text('SELECT (:signature = (' + MATCH_SCHEMA_SQL + '))'),
                                {'signature': MATCH_SCHEMA_SIGNATURE})
                            checks['database'] = result.scalar_one() is True
        except Exception as error:
            checks["database"] = False
            # Only a fixed code; no exception text, table names, DSNs or credentials.
            database_code = database_error_code(error)
    ready = checks["database"] if execution_mode() == "demo" else all(checks.values())
    content = {"status": "ready" if ready else "not_ready", "checks": checks}
    if offline:
        content['diagnostics'] = {
            'mode': 'saved-pilot-offline', 'required_checks': ['database'],
            'database_code': 'READY' if checks['database'] else database_code,
        }
    return JSONResponse(status_code=200 if ready else 503, content=content)
