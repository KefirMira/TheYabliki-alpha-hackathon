import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, event, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from repositories.analysis_tables import analysis_runs, company_news_analyses, insight_evidence, news_articles
from repositories.evidence_repository import EvidenceRepository
from services.company_analysis_service import AnalysisFailure, CompanyAnalysisService, RunStatusUncertain
from services.company_profile_service import CompanyNotFound


pytestmark = pytest.mark.integration


@pytest.fixture
def analysis_database(test_database_url):
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    tables = [insight_evidence, company_news_analyses, analysis_runs, news_articles]

    async def snapshot():
        async with engine.connect() as connection:
            result = {table.name: list((await connection.execute(select(table.c.id))).scalars()) for table in tables}
            result['jobs'] = list((await connection.execute(text('SELECT id FROM news_analysis_jobs'))).scalars())
            return result

    before = asyncio.run(snapshot())
    yield SimpleNamespace(engine=engine, sessions=async_sessionmaker(engine, expire_on_commit=False))

    async def cleanup():
        try:
            async with engine.begin() as connection:
                # Delete only this test's new coordination rows, before their history FKs.
                await connection.execute(text('DELETE FROM news_analysis_attempts WHERE NOT (run_id = ANY(:ids))'),
                                         {'ids':before['analysis_runs']})
                await connection.execute(text('DELETE FROM news_analysis_jobs WHERE NOT (id = ANY(:ids))'),
                                         {'ids':before['jobs']})
                for table in tables:
                    await connection.execute(delete(table).where(table.c.id.not_in(before[table.name])))
        finally:
            await engine.dispose()

    asyncio.run(cleanup())


async def state(engine):
    async with engine.connect() as connection:
        return {name: list((await connection.execute(text("SELECT * FROM public." + name + " ORDER BY id"))).mappings())
                for name in ["analysis_runs", "news_articles", "company_news_analyses", "insight_evidence"]}


def test_atomic_success_exact_evidence_and_no_connection_during_ai(analysis_database, bundle_factory):
    db = analysis_database
    checked_out = [0]
    event.listen(db.engine.sync_engine, "checkout", lambda *args: checked_out.__setitem__(0, checked_out[0] + 1))
    event.listen(db.engine.sync_engine, "checkin", lambda *args: checked_out.__setitem__(0, checked_out[0] - 1))
    bundle = bundle_factory()

    async def analyzer(**kwargs):
        assert checked_out[0] == 0
        running = await state(db.engine)
        assert running["analysis_runs"][-1]["status"] == "RUNNING"
        assert running["company_news_analyses"] == []
        assert checked_out[0] == 0
        return bundle

    async def scenario():
        saved = await CompanyAnalysisService(db.sessions, analyzer).analyze("SYNTH-COMPANY-A", bundle.analysis.news)
        rows = await state(db.engine)
        run = rows["analysis_runs"][-1]
        assert run["id"] == saved.run_id and run["status"] == "COMPLETED"
        assert run["finished_at"] >= run["started_at"]
        assert run["model_name"] == "synthetic-model"
        result = rows["company_news_analyses"][-1]
        assert result["risks"] == bundle.analysis.risks
        assert result["validation"] == bundle.analysis.validation.model_dump()
        assert result["confidence_score"] is None and result["impact_level"] is None
        assert result["evidence_strength"] is None and result["relevance_score"] is None
        assert result["source_snapshot"][0]["date"] == "2026-08"
        assert rows["news_articles"][-1]["content"] == bundle.analysis.news
        for row, fragment in zip(rows["insight_evidence"], bundle.evidence):
            assert row["evidence_text"] == fragment.text
            assert (row["document_name"], row["document_page"], row["chunk_id"]) == (fragment.document, fragment.page, fragment.chunk_id)
        assert rows["insight_evidence"][0]["document_date"] is None
        assert rows["insight_evidence"][1]["document_date"].isoformat() == "2026-08-12"

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["ai", "evidence"])
def test_failed_status_and_rollback_of_partial_results(analysis_database, bundle_factory, failure):
    db = analysis_database
    bundle = bundle_factory()

    async def analyzer(**kwargs):
        if failure == "ai":
            raise RuntimeError("Do not persist provider secrets")
        return bundle

    class BrokenEvidence(EvidenceRepository):
        async def create(self, insight_id, fragment):
            await super().create(insight_id, fragment)
            # Real FK failure after the first legitimate insert.
            await self.session.execute(text(
                "INSERT INTO insight_evidence(company_news_analysis_id,evidence_type,evidence_text) VALUES (-1,'PDF','Synthetic invalid FK')"
            ))

    async def scenario():
        with pytest.raises(AnalysisFailure) as error:
            await CompanyAnalysisService(db.sessions, analyzer, BrokenEvidence).analyze("SYNTH-COMPANY-A", bundle.analysis.news)
        rows = await state(db.engine)
        run = rows["analysis_runs"][-1]
        assert run["id"] == error.value.run_id and run["status"] == "FAILED"
        assert run["error_message"] == ("AI_ANALYSIS_FAILED" if failure == "ai" else "ANALYSIS_STORAGE_FAILED")
        assert run["finished_at"] is not None
        assert len(rows["news_articles"]) == 1
        assert rows["company_news_analyses"] == [] and rows["insight_evidence"] == []

    asyncio.run(scenario())


def test_missing_company_creates_no_run(analysis_database):
    async def scenario():
        with pytest.raises(CompanyNotFound):
            await CompanyAnalysisService(analysis_database.sessions).analyze("not-present", "Synthetic news")
        assert all(not rows for rows in (await state(analysis_database.engine)).values())

    asyncio.run(scenario())


def test_failure_to_record_failed_does_not_claim_success(analysis_database, monkeypatch):
    from repositories.analysis_run_repository import AnalysisRunRepository

    async def analyzer(**kwargs):
        raise RuntimeError("Synthetic provider failure")

    async def cannot_finish(*args, **kwargs):
        raise OSError("Synthetic unavailable database")

    monkeypatch.setattr(AnalysisRunRepository, "finish", cannot_finish)

    async def scenario():
        with pytest.raises(RunStatusUncertain):
            await CompanyAnalysisService(analysis_database.sessions, analyzer).analyze("SYNTH-COMPANY-A", "Synthetic news")
        rows = await state(analysis_database.engine)
        assert rows["analysis_runs"][-1]["status"] == "RUNNING"
        assert rows["company_news_analyses"] == []

    asyncio.run(scenario())
