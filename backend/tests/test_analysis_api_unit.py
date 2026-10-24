from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.exc import SQLAlchemyError

from api.company_analyses import get_analysis_service
from main import app
from services.company_analysis_service import AnalysisFailure, RunStatusUncertain, SavedAnalysis
from services.company_profile_service import CompanyNotFound


@pytest.fixture
def api_service(monkeypatch, bundle_factory):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    service = SimpleNamespace(analyze=AsyncMock(return_value=SavedAnalysis(1, 2, 3, bundle_factory())))
    app.dependency_overrides[get_analysis_service] = lambda: service
    yield service
    app.dependency_overrides.clear()


def test_analysis_api_response_and_input(api_service):
    with TestClient(app) as client:
        response = client.post("/api/companies/SYNTH-COMPANY-A/analyses", json={
            "news": {"text": "Synthetic persistence news", "title": "Synthetic title"},
        })
    assert response.status_code == 201
    data = response.json()
    assert (data["run_id"], data["insight_id"], data["news_id"]) == (1, 2, 3)
    assert data["status"] == "COMPLETED"
    assert data["company_id"] == "SYNTH-COMPANY-A"
    assert data["analysis"]["sources"][0]["document"] == "synthetic-month.pdf"
    api_service.analyze.assert_awaited_once_with("SYNTH-COMPANY-A", "Synthetic persistence news", "Synthetic title")


@pytest.mark.parametrize("payload", [
    {}, {"news": "wrong shape"}, {"news": {"text": ""}}, {"news": {"text": " \n "}},
    {"news": {"text": "Synthetic", "title": " "}}, {"news": {"text": "Synthetic", "confidence_score": 1}},
    {"news": {"text": "Synthetic"}, "company": {"company_id": "other"}},
])
def test_invalid_requests_do_not_start_ai(api_service, payload):
    with TestClient(app) as client:
        response = client.post("/api/companies/SYNTH-COMPANY-A/analyses", json=payload)
    assert response.status_code == 422
    api_service.analyze.assert_not_awaited()


@pytest.mark.parametrize("error,status,code", [
    (CompanyNotFound("missing"), 404, "COMPANY_NOT_FOUND"),
    (AnalysisFailure(7, "AI_ANALYSIS_FAILED"), 502, "AI_ANALYSIS_FAILED"),
    (AnalysisFailure(7, "ANALYSIS_STORAGE_FAILED"), 503, "ANALYSIS_STORAGE_FAILED"),
    (RunStatusUncertain(7, "RUN_STATUS_UNCERTAIN"), 503, "RUN_STATUS_UNCERTAIN"),
    (SQLAlchemyError("private internal error"), 503, "DATABASE_UNAVAILABLE"),
])
def test_safe_error_contract(api_service, error, status, code):
    api_service.analyze.side_effect = error
    with TestClient(app) as client:
        response = client.post("/api/companies/SYNTH-COMPANY-A/analyses", json={"news": {"text": "Synthetic"}})
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    assert "private internal error" not in response.text
    if isinstance(error, AnalysisFailure):
        assert response.json()["detail"]["run_id"] == 7


def test_missing_database_fails_without_importing_ai(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app) as client:
        response = client.post("/api/companies/SYNTH-COMPANY-A/analyses", json={"news": {"text": "Synthetic"}})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "DATABASE_UNAVAILABLE"
