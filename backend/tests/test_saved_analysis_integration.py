import asyncio

import httpx
import pytest
from sqlalchemy import event, text

from api.company_analyses import get_analysis_service
from db.session import get_company_session
from main import app
from repositories.evidence_repository import EvidenceRepository
from schemas.news import ExternalNewsInput
from services.company_analysis_service import CompanyAnalysisService
from services.news_ingestion_service import NewsIngestionService
from test_analysis_integration import analysis_database, state

pytestmark = pytest.mark.integration
NEWS_TEXT = "Synthetic stored news.\nExact second line with  two spaces."


async def create_news(db):
    return await NewsIngestionService(db.sessions).ingest(ExternalNewsInput(
        title="Synthetic saved title", content=NEWS_TEXT, url="https://example.invalid/saved",
        source_name="synthetic-saved", source_id="Saved-A", language="ru", published_at="2026-01-01T12:00:00+03:00"))


async def snapshot(db):
    async with db.engine.connect() as connection:
        return await connection.scalar(text("SELECT jsonb_agg(to_jsonb(n) ORDER BY id)::text FROM news_articles n"))


@pytest.mark.parametrize("failure", [None, "ai", "evidence"])
def test_one_news_two_companies_atomic_statuses_and_gets(analysis_database, bundle_factory, monkeypatch, failure):
    db = analysis_database
    monkeypatch.setenv("AI_MODE", "full")
    checked_out = [0]
    event.listen(db.engine.sync_engine, "checkout", lambda *args: checked_out.__setitem__(0, checked_out[0] + 1))
    event.listen(db.engine.sync_engine, "checkin", lambda *args: checked_out.__setitem__(0, checked_out[0] - 1))
    async def analyzer(*, news, company):
        assert checked_out[0] == 0 and news == NEWS_TEXT
        current = await state(db.engine)
        assert current["analysis_runs"][-1]["status"] == "RUNNING"
        assert checked_out[0] == 0
        if failure == "ai" and company.company_id.endswith("B"):
            raise RuntimeError("Synthetic AI failure")
        bundle = bundle_factory(news=news, company_id=company.company_id)
        bundle.analysis.summary = f"Synthetic summary for {company.company_id}"
        return bundle

    class Evidence(EvidenceRepository):
        async def create(self, insight_id, fragment):
            result = await super().create(insight_id, fragment)
            if failure == "evidence":
                # Fail on company B after at least one legitimate evidence INSERT.
                company = await self.session.scalar(text("SELECT c.source_id FROM company_news_analyses a JOIN companies c ON c.id=a.company_id WHERE a.id=:id"), {"id": insight_id})
                if company.endswith("B"):
                    raise RuntimeError("Synthetic evidence write failure")
            return result

    service = CompanyAnalysisService(db.sessions, analyzer, Evidence)
    app.dependency_overrides[get_analysis_service] = lambda: service
    async def read_session():
        async with db.sessions() as session:
            yield session
    app.dependency_overrides[get_company_session] = read_session

    async def scenario():
        saved_news = await create_news(db)
        before = await snapshot(db)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            a = await client.post(f"/api/companies/SYNTH-COMPANY-A/news/{saved_news.news_id}/analyses")
            b = await client.post(f"/api/companies/SYNTH-COMPANY-B/news/{saved_news.news_id}/analyses")
            assert a.status_code == 201
            assert b.status_code == (201 if failure is None else 502 if failure == "ai" else 503)
            rows = await state(db.engine)
            assert await snapshot(db) == before  # Includes ALL news metadata and timestamps.
            assert len(rows["news_articles"]) == 1
            assert len(rows["analysis_runs"]) == 2
            assert rows["analysis_runs"][0]["status"] == "COMPLETED"
            assert rows["analysis_runs"][1]["status"] == ("COMPLETED" if failure is None else "FAILED")
            expected = 2 if failure is None else 1
            assert len(rows["company_news_analyses"]) == expected
            assert len(rows["insight_evidence"]) == expected * 2
            assert all(row["news_id"] == saved_news.news_id for row in rows["company_news_analyses"])
            if failure is None:
                assert a.json()["run_id"] != b.json()["run_id"]
                assert a.json()["analysis"]["summary"] != b.json()["analysis"]["summary"]
            for suffix, response in (("A", a), ("B", b)):
                feed = await client.get(f"/api/companies/SYNTH-COMPANY-{suffix}/insights")
                assert feed.status_code == 200
                assert len(feed.json()["items"]) == (1 if suffix == "A" or failure is None else 0)
                if response.status_code == 201:
                    card = await client.get(f"/api/companies/SYNTH-COMPANY-{suffix}/insights/{response.json()['insight_id']}")
                    assert card.status_code == 200 and card.json()["news"]["text"] == NEWS_TEXT
                    assert card.json()["news"]["title"] == "Synthetic saved title"
                    assert len(card.json()["evidence"]) == 2
            foreign = await client.get(f"/api/companies/SYNTH-COMPANY-B/insights/{a.json()['insight_id']}")
            assert foreign.status_code == 404
    try:
        asyncio.run(scenario())
    finally:
        app.dependency_overrides.pop(get_analysis_service, None)
        app.dependency_overrides.pop(get_company_session, None)


@pytest.mark.parametrize("missing", ["company", "news", "both"])
def test_missing_records_create_no_run(analysis_database, monkeypatch, missing):
    db = analysis_database
    monkeypatch.setenv("AI_MODE", "full")
    async def no_ai(**kwargs):
        pytest.fail("AI must not run for missing records")
    app.dependency_overrides[get_analysis_service] = lambda: CompanyAnalysisService(db.sessions, no_ai)
    async def scenario():
        saved = await create_news(db)
        before = await snapshot(db)
        company = "absent" if missing in {"company", "both"} else "SYNTH-COMPANY-A"
        news_id = 9223372036854775807 if missing in {"news", "both"} else saved.news_id
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            result = await client.post(f"/api/companies/{company}/news/{news_id}/analyses")
        assert result.status_code == 404
        assert result.json()["detail"]["code"] == ("NEWS_NOT_FOUND" if missing == "news" else "COMPANY_NOT_FOUND")
        assert (await state(db.engine))["analysis_runs"] == []
        assert await snapshot(db) == before
    try:
        asyncio.run(scenario())
    finally:
        app.dependency_overrides.pop(get_analysis_service, None)
