import asyncio
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from api.company_analyses import get_analysis_analyzer, get_analysis_service
from main import app
from repositories.evidence_repository import EvidenceRepository
from services.company_analysis_service import CompanyAnalysisService
from test_analysis_integration import analysis_database, state


pytestmark = pytest.mark.integration


@pytest.mark.parametrize("failure", [None, "ai", "evidence"])
def test_http_analysis_real_transactions(monkeypatch, analysis_database, test_database_url, bundle_factory, failure):
    db = analysis_database
    news = "Synthetic persistence news"
    analyzer = AsyncMock(return_value=bundle_factory(news))
    if failure == "ai":
        analyzer.side_effect = RuntimeError("Sensitive synthetic provider message")

    class BrokenEvidence(EvidenceRepository):
        async def create(self, insight_id, fragment):
            await super().create(insight_id, fragment)
            await self.session.execute(text("SELECT 1/0"))

    monkeypatch.setenv("DATABASE_URL", test_database_url)
    app.dependency_overrides[get_analysis_analyzer] = lambda: analyzer
    if failure == "evidence":
        app.dependency_overrides[get_analysis_service] = lambda: CompanyAnalysisService(db.sessions, analyzer, BrokenEvidence)
    try:
        with TestClient(app) as client:
            response = client.post("/api/companies/SYNTH-COMPANY-A/analyses", json={"news": {"text": news}})
            missing = client.post("/api/companies/not-present/analyses", json={"news": {"text": news}})
        assert missing.status_code == 404
        assert analyzer.await_count == 1
        rows = asyncio.run(state(db.engine))
        run = rows["analysis_runs"][-1]
        if failure is None:
            assert response.status_code == 201
            body = response.json()
            assert body["run_id"] == run["id"] and run["status"] == "COMPLETED"
            assert body["insight_id"] == rows["company_news_analyses"][-1]["id"]
            assert rows["insight_evidence"][0]["evidence_text"] == bundle_factory().evidence[0].text
        else:
            assert response.status_code == (502 if failure == "ai" else 503)
            assert run["status"] == "FAILED"
            assert response.json()["detail"]["run_id"] == run["id"]
            assert rows["company_news_analyses"] == [] and rows["insight_evidence"] == []
            assert "Sensitive synthetic provider message" not in response.text
    finally:
        app.dependency_overrides.clear()
