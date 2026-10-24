import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from api.company_analyses import get_analysis_service
from main import app
from repositories.company_repository import CompanyRecord
from services import company_analysis_service as module
from services.company_analysis_service import (
    AnalysisFailure, CompanyAnalysisService, NewsNotAnalyzable, NewsNotFound, RunStatusUncertain, SavedAnalysis,
)
from services.company_profile_service import CompanyNotFound


@pytest.fixture
def saved_api(monkeypatch, bundle_factory):
    monkeypatch.setenv("AI_MODE", "full")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    service = AsyncMock()
    service.analyze_saved.return_value = SavedAnalysis(1, 2, 3, bundle_factory())
    app.dependency_overrides[get_analysis_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_analysis_service, None)


def test_saved_http_response_and_openapi(saved_api):
    with TestClient(app) as client:
        response = client.post("/api/companies/SYNTH-COMPANY-A/news/3/analyses")
        spec = client.get("/openapi.json").json()
    assert response.status_code == 201
    assert response.json()["news_id"] == 3 and response.json()["status"] == "COMPLETED"
    saved_api.analyze_saved.assert_awaited_once_with("SYNTH-COMPANY-A", 3)
    operation = spec["paths"]["/api/companies/{source_id}/news/{news_id}/analyses"]["post"]
    assert "requestBody" not in operation
    assert {"201", "404", "422", "502", "503"} <= set(operation["responses"])


@pytest.mark.parametrize("error,status,code", [
    (CompanyNotFound(), 404, "COMPANY_NOT_FOUND"), (NewsNotFound(), 404, "NEWS_NOT_FOUND"),
    (NewsNotAnalyzable(), 422, "NEWS_CONTENT_UNAVAILABLE"),
    (AnalysisFailure(7, "AI_ANALYSIS_FAILED"), 502, "AI_ANALYSIS_FAILED"),
    (AnalysisFailure(7, "ANALYSIS_STORAGE_FAILED"), 503, "ANALYSIS_STORAGE_FAILED"),
    (RunStatusUncertain(7, "RUN_STATUS_UNCERTAIN"), 503, "RUN_STATUS_UNCERTAIN"),
    (OSError("secret DSN"), 503, "DATABASE_UNAVAILABLE"),
])
def test_saved_http_errors(saved_api, error, status, code):
    saved_api.analyze_saved.side_effect = error
    with TestClient(app) as client:
        response = client.post("/api/companies/company/news/3/analyses")
    assert response.status_code == status and response.json()["detail"]["code"] == code
    assert "secret" not in response.text


@pytest.mark.parametrize("news_id", ["0", "-1", "not-an-id", "9223372036854775808"])
def test_saved_http_invalid_id(saved_api, news_id):
    with TestClient(app) as client:
        response = client.post(f"/api/companies/company/news/{news_id}/analyses")
    assert response.status_code == 422
    saved_api.analyze_saved.assert_not_awaited()


def test_saved_demo_cannot_reach_service(saved_api, monkeypatch):
    monkeypatch.setenv("AI_MODE", "demo")
    with TestClient(app) as client:
        response = client.post("/api/companies/company/news/3/analyses")
    assert response.status_code == 503 and response.json()["detail"]["code"] == "AI_DISABLED_IN_DEMO"
    saved_api.analyze_saved.assert_not_awaited()


@pytest.mark.parametrize("condition", ["company_missing", "news_missing", "null", "blank", "large"])
def test_saved_preconditions_never_create_run(monkeypatch, condition):
    @asynccontextmanager
    async def transaction():
        yield
    class Session:
        begin = staticmethod(transaction)
    @asynccontextmanager
    async def sessions():
        yield Session()
    company = CompanyRecord(1, "A", "Synthetic", None, None, None, None, None)
    companies = AsyncMock()
    companies.get_by_source_id.return_value = None if condition == "company_missing" else company
    news = AsyncMock()
    news.get_by_id.return_value = None if condition == "news_missing" else {
        "content": None if condition == "null" else "x" * 100001 if condition == "large" else " \n"}
    runs = AsyncMock()
    monkeypatch.setattr(module, "CompanyRepository", lambda session: companies)
    monkeypatch.setattr(module, "NewsRepository", lambda session: news)
    monkeypatch.setattr(module, "AnalysisRunRepository", lambda session: runs)
    analyzer = AsyncMock()
    expected = CompanyNotFound if condition == "company_missing" else NewsNotFound if condition == "news_missing" else NewsNotAnalyzable
    with pytest.raises(expected):
        asyncio.run(CompanyAnalysisService(sessions, analyzer).analyze_saved("A", 1))
    runs.start.assert_not_awaited()
    news.create_manual.assert_not_awaited()
    analyzer.assert_not_awaited()
