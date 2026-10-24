"""Pure policy and HTTP contract tests; auth overrides are explicit and local here."""
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from api.auth import company_read
from db.session import get_company_session
from main import app
from services import capabilities_service as module
from services.company_context_service import CompanyContextExternalTransferBlocked, external_transfer_guard


def codes(capability):
    return {reason.code for reason in capability.reasons}


@pytest.mark.parametrize("mode", ["demo", "full"])
@pytest.mark.parametrize("can_analyze", [False, True])
def test_shared_policy_is_conservative(monkeypatch, mode, can_analyze):
    monkeypatch.setenv("AI_MODE", mode)
    monkeypatch.setenv("LLM_API_KEY", "synthetic-credential-not-to-return")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.invalid/private-provider")
    result = module.describe_capabilities("SYNTH-A", can_analyze=can_analyze)
    ops = result.operations
    assert ops.read_profile.state == ops.read_insights.state == ops.submit_news.state == "AVAILABLE"
    assert ops.analyze_new.state == "BLOCKED"
    assert "COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED" in codes(ops.analyze_new)
    assert ("ANALYSIS_PERMISSION_REQUIRED" in codes(ops.analyze_new)) is (not can_analyze)
    assert ("AI_DISABLED_IN_DEMO" in codes(ops.analyze_new)) is (mode == "demo")
    assert ("DEMO_SYNTHETIC_NEWS_ONLY" in ops.submit_news.conditions) is (mode == "demo")
    assert ops.reuse_completed.state == ("UNKNOWN" if mode == "full" and can_analyze else "BLOCKED")
    assert ops.retry_analysis.state == "UNAVAILABLE"
    assert codes(ops.retry_analysis) == {"ADMINISTRATIVE_RETRY_ONLY"}
    assert result.external_provider.state == "UNKNOWN"
    assert "synthetic-credential" not in result.model_dump_json()
    assert "private-provider" not in result.model_dump_json()


def test_future_guard_permission_does_not_promise_provider_execution(monkeypatch):
    monkeypatch.setenv("AI_MODE", "full")
    monkeypatch.setattr(module, "external_transfer_guard", lambda context: None)
    result = module.describe_capabilities("SYNTH-A", can_analyze=True)
    assert result.operations.analyze_new.state == "UNKNOWN"
    assert codes(result.operations.analyze_new) == {"EXECUTION_PREREQUISITES_NOT_EVALUATED"}


def test_real_transfer_guard_still_blocks_non_none():
    external_transfer_guard(None)
    with pytest.raises(CompanyContextExternalTransferBlocked):
        external_transfer_guard({})


def test_invalid_mode_never_produces_capabilities(monkeypatch):
    monkeypatch.setenv("AI_MODE", "invalid")
    with pytest.raises(ValueError):
        module.describe_capabilities("SYNTH-A", can_analyze=True)


@pytest.mark.parametrize("read_allowed,write_allowed", [(False, False), (True, False), (True, True)])
def test_service_reuses_acl_repository(monkeypatch, read_allowed, write_allowed):
    monkeypatch.setenv("AI_MODE", "full")
    seen = []
    class Repository:
        def __init__(self, session):
            assert session is marker
        async def company_allowed(self, user, source, write=False):
            seen.append((user, source, write))
            return write_allowed if write else read_allowed
    marker = object()
    monkeypatch.setattr(module, "AuthRepository", Repository)
    service = module.CompanyCapabilitiesService(marker)
    user = uuid4()
    if not read_allowed:
        with pytest.raises(HTTPException) as error:
            asyncio.run(service.get("SYNTH-A", user))
        assert error.value.status_code == 403
        assert len(seen) == 1
    else:
        result = asyncio.run(service.get("SYNTH-A", user))
        assert seen == [(user, "SYNTH-A", False), (user, "SYNTH-A", True)]
        assert result.operations.reuse_completed.state == ("UNKNOWN" if write_allowed else "BLOCKED")


@pytest.mark.parametrize("token", [None, "malformed"])
def test_anonymous_and_malformed_are_401_without_database(monkeypatch, token):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app) as client:
        response = client.get("/api/companies/SYNTH-A/capabilities", headers={} if token is None else {"Authorization": "Bearer " + token})
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.headers["Cache-Control"] == "no-store"


def test_database_failure_has_safe_503(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    actor = SimpleNamespace(user_id=uuid4())
    async def fail(*args):
        raise SQLAlchemyError("synthetic connection detail MUST NOT BE RETURNED")
    monkeypatch.setattr(module.CompanyCapabilitiesService, "get", fail)
    app.dependency_overrides[company_read] = lambda: actor
    app.dependency_overrides[get_company_session] = lambda: object()
    try:
        with TestClient(app) as client:
            response = client.get("/api/companies/SYNTH-A/capabilities")
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "DATABASE_UNAVAILABLE"
        assert "MUST NOT" not in response.text
    finally:
        app.dependency_overrides.pop(company_read)
        app.dependency_overrides.pop(get_company_session)


def test_openapi_capabilities_security_and_limitations():
    op = app.openapi()["paths"]["/api/companies/{source_id}/capabilities"]["get"]
    assert op["security"] == [{"HTTPBearer": []}]
    assert set(op["responses"]) == {"200", "401", "403", "422", "503"}
    assert "requestBody" not in op
    assert "UNKNOWN" in op["description"] and "COMPLETED" in op["description"]
    for status in ("401", "403", "503"):
        assert op["responses"][status]["description"]
