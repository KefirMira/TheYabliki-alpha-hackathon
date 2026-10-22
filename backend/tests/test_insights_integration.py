import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from main import app
from services.company_analysis_service import CompanyAnalysisService
from test_analysis_integration import analysis_database


pytestmark = pytest.mark.integration
COMPANY = "SYNTH-COMPANY-A"


async def save(db, bundle_factory, company=COMPANY):
    news = "Synthetic history news"

    async def analyzer(**kwargs):
        return bundle_factory(news, company)

    return await CompanyAnalysisService(db.sessions, analyzer).analyze(company, news)


def test_empty_history_and_missing_company(monkeypatch, analysis_database, test_database_url):
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    with TestClient(app) as client:
        response = client.get(f"/api/companies/{COMPANY}/insights")
        assert response.json() == {"items": [], "next_cursor": None}
        assert client.get("/api/companies/not-present/insights").status_code == 404
        assert client.get(f"/api/companies/{COMPANY}/insights/999999").json()["detail"]["code"] == "INSIGHT_NOT_FOUND"
        assert client.get("/api/companies/not-present/insights/1").json()["detail"]["code"] == "COMPANY_NOT_FOUND"


def test_card_returns_stored_data_and_isolates_company(monkeypatch, analysis_database, test_database_url, bundle_factory):
    db = analysis_database
    saved = asyncio.run(save(db, bundle_factory))
    foreign = asyncio.run(save(db, bundle_factory, "SYNTH-COMPANY-B"))
    forbidden_ai = AsyncMock(side_effect=AssertionError("History must not run AI"))
    monkeypatch.setattr(CompanyAnalysisService, "analyze", forbidden_ai)
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    with TestClient(app) as client:
        response = client.get(f"/api/companies/{COMPANY}/insights/{saved.insight_id}")
        assert response.status_code == 200
        card = response.json()
        assert card["run_id"] == saved.run_id and card["status"] == "COMPLETED"
        assert card["type"] is None
        assert card["risks"] == saved.result.analysis.risks
        assert card["opportunities"] == saved.result.analysis.opportunities
        assert card["recommendations"] == saved.result.analysis.recommendations
        assert card["validation"] == saved.result.analysis.validation.model_dump()
        assert card["sources"][0]["date"] == "2026-08"
        assert card["evidence"][0]["text"] == saved.result.evidence[0].text
        assert card["evidence"][0]["document_date"] is None
        assert card["evidence"][1]["document_date"] == "2026-08-12"
        assert card["news"]["text"] == "Synthetic history news"
        assert not {"confidence_score", "impact_level", "evidence_strength"} & card.keys()
        for company, identifier in [(COMPANY, foreign.insight_id), ("SYNTH-COMPANY-B", saved.insight_id)]:
            assert client.get(f"/api/companies/{company}/insights/{identifier}").status_code == 404
        assert [x["insight_id"] for x in client.get(f"/api/companies/{COMPANY}/insights").json()["items"]] == [saved.insight_id]
    forbidden_ai.assert_not_awaited()


@pytest.mark.parametrize("status", ["RUNNING", "PENDING", "FAILED"])
def test_non_completed_results_are_not_exposed(monkeypatch, analysis_database, test_database_url, bundle_factory, status):
    db = analysis_database
    saved = asyncio.run(save(db, bundle_factory))

    async def change_status():
        async with db.engine.begin() as connection:
            await connection.execute(text("UPDATE analysis_runs SET status=:status WHERE id=:id"), {"status": status, "id": saved.run_id})

    asyncio.run(change_status())
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    with TestClient(app) as client:
        assert client.get(f"/api/companies/{COMPANY}/insights").json()["items"] == []
        assert client.get(f"/api/companies/{COMPANY}/insights/{saved.insight_id}").status_code == 404


def test_keyset_sorting_ties_and_insert_between_pages(monkeypatch, analysis_database, test_database_url, bundle_factory):
    db = analysis_database
    stamp = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=timezone.utc)

    async def seed():
        saved = [await save(db, bundle_factory) for _ in range(5)]
        async with db.engine.begin() as connection:
            for index, item in enumerate(saved):
                await connection.execute(text("UPDATE company_news_analyses SET created_at=:stamp WHERE id=:id"), {
                    "stamp": stamp if index < 3 else stamp + timedelta(seconds=1), "id": item.insight_id,
                })
            await connection.execute(text("UPDATE company_news_analyses SET insight_kind='risk' WHERE id=:id"), {"id": saved[-1].insight_id})
        return saved

    saved = asyncio.run(seed())
    expected = [item.insight_id for item in reversed(saved)]
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    with TestClient(app) as client:
        first = client.get(f"/api/companies/{COMPANY}/insights", params={"limit": 2}).json()
        assert [row["insight_id"] for row in first["items"]] == expected[:2]
        assert first["items"][0]["type"] == "risk"
        assert first["next_cursor"] is not None
        # A newly inserted head item must not shift the continuation page.
        new_item = asyncio.run(save(db, bundle_factory))
        seen = [row["insight_id"] for row in first["items"]]
        cursor = first["next_cursor"]
        for _ in range(4):
            page_response = client.get(f"/api/companies/{COMPANY}/insights", params={"limit": 2, "cursor": cursor})
            assert page_response.status_code == 200
            page = page_response.json()
            seen.extend(row["insight_id"] for row in page["items"])
            cursor = page["next_cursor"]
            if cursor is None:
                break
        assert seen == expected and len(set(seen)) == 5
        assert new_item.insight_id not in seen and cursor is None
        foreign_response = client.get("/api/companies/SYNTH-COMPANY-B/insights", params={"cursor": first["next_cursor"]})
        assert foreign_response.status_code == 422
        assert len(client.get(f"/api/companies/{COMPANY}/insights", params={"limit": 100}).json()["items"]) == 6
