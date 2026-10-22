"""Readiness is local/configuration validation, never a paid provider probe."""
import asyncio
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from services.knowledge_base_service import load_knowledge_base
from settings import execution_mode

router = APIRouter()
TABLES = (
    "companies", "persons", "company_person_links", "company_payments",
    "news_articles", "analysis_runs", "company_news_analyses", "insight_evidence",
    "information_sources", "company_contexts", "company_documents",
    "company_insight_states", "insight_updates",
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


@router.get("/ready")
async def readiness(request: Request):
    checks = {
        "rag": await asyncio.to_thread(rag_ready),
        "llm_config": all(os.environ.get(k, "").strip() for k in
                          ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")),
        "database": False,
    }
    sessions = getattr(request.app.state, "company_sessions", None)
    if sessions is not None:
        try:
            async with asyncio.timeout(6):
                async with sessions() as session:
                    for table in TABLES:
                        result = await session.execute(
                            text("SELECT to_regclass(:name)"), {"name": f"public.{table}"}
                        )
                        if result.scalar_one() is None:
                            break
                    else:
                        checks["database"] = True
        except Exception:
            # No paths, DSNs, SQL or provider credentials in public diagnostics.
            pass
    ready = checks["database"] if execution_mode() == "demo" else all(checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )
