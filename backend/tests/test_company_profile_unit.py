import asyncio
from dataclasses import replace
from decimal import Decimal
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError

from db.session import get_company_session
from main import app
from repositories.company_repository import CompanyRecord, CompanyRepository
from services.company_profile_service import (
    CompanyNotFound,
    CompanyProfileService,
    to_company_profile,
    to_profile_response,
)


@pytest.fixture
def record():
    return CompanyRecord(
        id=7,
        source_id="SYNTH-PROFILE-A",
        name="Synthetic Workshop",
        industry="Test industry",
        region="Test region",
        revenue=Decimal("9999999999999999.99"),
        revenue_year=2025,
        client_status="CLIENT",
    )


def test_api_keeps_decimal_precision(record):
    response = to_profile_response(record)
    assert response.revenue == record.revenue
    assert response.model_dump(mode="json")["revenue"] == "9999999999999999.99"
    assert response.credit_exposure is None


@pytest.mark.parametrize("name", ["SYNTH-PROFILE-A", " SYNTH-PROFILE-A ", " "])
def test_technical_or_blank_name_is_not_a_company_name(record, name):
    response = to_profile_response(replace(record, name=name))
    assert response.name is None
    assert response.name_is_placeholder is True


def test_real_name_and_unknown_values(record):
    response = to_profile_response(replace(record, revenue=None, region=None))
    assert response.name == "Synthetic Workshop"
    assert response.name_is_placeholder is False
    assert response.model_dump(mode="json")["revenue"] is None
    assert response.region is None


def test_ai_compatibility_adapter(record):
    profile = to_company_profile(replace(record, revenue=Decimal("1234.56")))
    assert profile.company_id == record.source_id
    assert profile.industry == record.industry
    assert profile.region == record.region
    assert profile.revenue == 1234.56
    assert profile.credit_exposure is None
    assert to_company_profile(replace(record, revenue=None)).revenue is None


def test_service_raises_not_found():
    repository = Mock()
    repository.get_by_source_id = AsyncMock(return_value=None)
    with pytest.raises(CompanyNotFound):
        asyncio.run(CompanyProfileService(repository).get_record("missing"))


def test_service_returns_ai_profile(record):
    repository = Mock()
    repository.get_by_source_id = AsyncMock(return_value=record)
    profile = asyncio.run(CompanyProfileService(repository).get_profile(record.source_id))
    assert profile.company_id == record.source_id
    assert profile.credit_exposure is None


@pytest.mark.parametrize("found", [True, False])
def test_repository_uses_bound_source_id(record, found):
    result = Mock()
    result.mappings.return_value.one_or_none.return_value = vars(record) if found else None
    session = Mock()
    session.execute = AsyncMock(return_value=result)
    value = "synthetic' OR true --"
    actual = asyncio.run(CompanyRepository(session).get_by_source_id(value))
    assert actual == (record if found else None)
    statement = session.execute.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    assert value not in str(compiled)
    assert value in compiled.params.values()
    assert "public.companies" in str(compiled)


def test_main_imports_without_llm_key_or_ai_services():
    env = dict(os.environ, PYTHON_DOTENV_DISABLED="1")
    for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        env.pop(key, None)
    result = subprocess.run(
        [sys.executable, "-B", "-c",
         "import main, sys; assert 'openai' not in sys.modules; "
         "assert 'services.rag_service' not in sys.modules; "
         "assert 'services.personalization_service' not in sys.modules"],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_unconfigured_database_returns_503_without_breaking_health(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        response = client.get("/api/companies/SYNTH-PROFILE-A")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "DATABASE_UNAVAILABLE"


def test_missing_company_returns_404(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    result = Mock()
    result.mappings.return_value.one_or_none.return_value = None
    session = Mock()
    session.execute = AsyncMock(return_value=result)

    async def session_override():
        yield session

    app.dependency_overrides[get_company_session] = session_override
    try:
        with TestClient(app) as client:
            response = client.get("/api/companies/not-present")
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "COMPANY_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("error", [SQLAlchemyError("internal details"), OSError("internal details"), TimeoutError("internal details")])
def test_database_errors_are_sanitized(monkeypatch, error):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    class BrokenSession:
        async def __aenter__(self):
            raise error

        async def __aexit__(self, *args):
            pass

    with TestClient(app) as client:
        app.state.company_sessions = BrokenSession
        response = client.get("/api/companies/SYNTH-PROFILE-A")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "DATABASE_UNAVAILABLE"
    assert "internal details" not in response.text


@pytest.mark.parametrize("failure,expected_status", [(None, 200), (ValueError("No context"), 422), (RuntimeError("Provider failure"), 502)])
def test_existing_company_analysis_contract_without_llm(monkeypatch, failure, expected_status):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    result = {
        "company_id": "SYNTH-LEGACY",
        "news": "Synthetic news",
        "relevance": "low",
        "summary": "Synthetic summary",
        "risks": [], "opportunities": [], "recommendations": [],
        "sources": [{"id": 1, "document": "synthetic.pdf", "page": 1, "score": 0.1}],
        "validation": {"passed": True, "warnings": []},
    }
    module = ModuleType("services.personalization_service")
    module.analyze_for_company = AsyncMock(return_value=result, side_effect=failure)
    monkeypatch.setitem(sys.modules, "services.personalization_service", module)
    with TestClient(app) as client:
        response = client.post("/api/analyze-company", json={
            "news": "Synthetic news", "company": {"company_id": "SYNTH-LEGACY"},
        })
    assert response.status_code == expected_status
    if failure is None:
        assert response.json() == result
    kwargs = module.analyze_for_company.await_args.kwargs
    assert kwargs["news"] == "Synthetic news"
    assert kwargs["company"].company_id == "SYNTH-LEGACY"
