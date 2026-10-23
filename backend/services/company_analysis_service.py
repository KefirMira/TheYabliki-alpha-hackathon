"""Commit RUNNING first, release the DB during AI, commit result atomically."""

import asyncio
from dataclasses import dataclass

from repositories.analysis_run_repository import AnalysisRunRepository
from repositories.company_analysis_repository import CompanyAnalysisRepository
from repositories.company_repository import CompanyRepository
from repositories.evidence_repository import EvidenceRepository
from repositories.news_repository import NewsRepository
from schemas.persisted_analysis import PersistableAnalysis
from services.company_profile_service import CompanyNotFound, to_company_profile


class AnalysisFailure(Exception):
    def __init__(self, run_id: int, code: str):
        self.run_id = run_id
        self.code = code
        super().__init__(code)


class RunStatusUncertain(AnalysisFailure):
    pass


class NewsNotFound(Exception):
    pass


class NewsNotAnalyzable(Exception):
    pass


@dataclass(frozen=True)
class SavedAnalysis:
    run_id: int
    insight_id: int
    news_id: int
    result: PersistableAnalysis


async def default_analyzer(*, news, company):
    from services.personalization_service import analyze_for_company_with_evidence

    return await analyze_for_company_with_evidence(news, company)


class CompanyAnalysisService:
    def __init__(self, sessions, analyzer=default_analyzer, evidence_repository=EvidenceRepository):
        self.sessions = sessions
        self.analyzer = analyzer
        self.evidence_repository = evidence_repository

    async def analyze(self, source_id: str, news: str, title: str | None = None) -> SavedAnalysis:
        if not news.strip():
            raise ValueError("News text must not be blank")
        async with self.sessions() as session:
            async with session.begin():
                record = await CompanyRepository(session).get_by_source_id(source_id)
                if record is None:
                    raise CompanyNotFound(source_id)
                news_id = await NewsRepository(session).create_manual(news, title)
                run_id = await AnalysisRunRepository(session).start(record.id)
        return await self._execute(source_id, news, record, news_id, run_id)

    async def analyze_saved(self, source_id: str, news_id: int) -> SavedAnalysis:
        async with self.sessions() as session:
            async with session.begin():
                record = await CompanyRepository(session).get_by_source_id(source_id)
                if record is None:
                    raise CompanyNotFound(source_id)
                stored = await NewsRepository(session).get_by_id(news_id)
                if stored is None:
                    raise NewsNotFound(news_id)
                news = stored["content"]
                if not isinstance(news, str) or not news.strip() or len(news) > 100_000:
                    raise NewsNotAnalyzable(news_id)
                run_id = await AnalysisRunRepository(session).start(record.id)
        return await self._execute(source_id, news, record, news_id, run_id)

    async def _execute(self, source_id, news, record, news_id, run_id) -> SavedAnalysis:
        # No session or transaction survives this boundary.
        phase = "AI_ANALYSIS_FAILED"
        try:
            bundle = PersistableAnalysis.model_validate(await self.analyzer(
                news=news, company=to_company_profile(record),
            ))
            if bundle.analysis.company_id != source_id or bundle.analysis.news != news:
                raise ValueError("Analysis does not match its input")
            phase = "ANALYSIS_STORAGE_FAILED"
            async with self.sessions() as session:
                async with session.begin():
                    insight_id = await CompanyAnalysisRepository(session).create(run_id, record.id, news_id, bundle)
                    for fragment in bundle.evidence:
                        await self.evidence_repository(session).create(insight_id, fragment)
                    await AnalysisRunRepository(session).finish(
                        run_id, "COMPLETED", model_name=bundle.model_name,
                        prompt_version=bundle.prompt_version, result_summary=bundle.analysis.summary,
                    )
            return SavedAnalysis(run_id, insight_id, news_id, bundle)
        except (Exception, asyncio.CancelledError) as error:
            try:
                async with self.sessions() as session:
                    async with session.begin():
                        await AnalysisRunRepository(session).finish(run_id, "FAILED", error_message=phase)
            except Exception as status_error:
                # Never claim FAILED if its transaction could not be committed.
                raise RunStatusUncertain(run_id, "RUN_STATUS_UNCERTAIN") from status_error
            if isinstance(error, asyncio.CancelledError):
                raise
            raise AnalysisFailure(run_id, phase) from error
