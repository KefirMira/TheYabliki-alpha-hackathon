"""Commit RUNNING first, release the DB during AI, commit result atomically."""

from repositories.auth_repository import AuthRepository
from services.auth_service import denied

import asyncio
from dataclasses import dataclass

from repositories.analysis_run_repository import AnalysisRunRepository
from repositories.company_analysis_repository import CompanyAnalysisRepository
from repositories.company_repository import CompanyRepository
from repositories.evidence_repository import EvidenceRepository
from repositories.news_repository import NewsRepository
from repositories.news_analysis_job_repository import AnalysisConflict, NewsAnalysisJobRepository
from schemas.company_analysis_api import CreatedCompanyAnalysis
from schemas.persisted_analysis import PersistableAnalysis
from services.protected_ai import invoke
from services.company_profile_service import CompanyNotFound, to_company_profile
from services.company_context_service import load_company_context, external_transfer_guard


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
    result: PersistableAnalysis | None
    cached_response: CreatedCompanyAnalysis | None = None
    reused: bool = False


def cached_analysis(payload, reused=True):
    response = CreatedCompanyAnalysis.model_validate(payload)
    return SavedAnalysis(response.run_id, response.insight_id, response.news_id, None, response, reused)


async def default_analyzer(*, news, company):
    # Fail before importing the SDK or creating an external client.
    external_transfer_guard(company._ai_context)
    from services.personalization_service import analyze_for_company_with_evidence

    return await analyze_for_company_with_evidence(news, company)


class CompanyAnalysisService:
    def __init__(self, sessions, analyzer=default_analyzer, evidence_repository=EvidenceRepository,
                 context_loader=load_company_context, actor_id=None):
        self.sessions = sessions
        self.actor_id = actor_id
        self.analyzer = analyzer
        self.evidence_repository = evidence_repository
        self.context_loader = context_loader

    async def _profile_for_analysis(self, session, record):
        company = to_company_profile(record)
        company._ai_context = await self.context_loader(session, record)
        if self.analyzer is default_analyzer:
            external_transfer_guard(company._ai_context)
        return company

    async def analyze(self, source_id: str, news: str, title: str | None = None) -> SavedAnalysis:
        if not news.strip():
            raise ValueError("News text must not be blank")
        async with self.sessions() as session:
            async with session.begin():
                if self.actor_id is not None and not await AuthRepository(session).company_allowed(self.actor_id, source_id, True):
                    raise denied()
                record = await CompanyRepository(session).get_by_source_id(source_id)
                if record is None:
                    raise CompanyNotFound(source_id)
                company = await self._profile_for_analysis(session, record)
                news_id = await NewsRepository(session).create_manual(news, title)
                if self.actor_id is not None:
                    await AuthRepository(session).grant_news(self.actor_id, news_id)
                run_id = await AnalysisRunRepository(session).start(record.id)
        return await self._execute(source_id, news, record, news_id, run_id, company=company)

    async def analyze_saved(self, source_id: str, news_id: int) -> SavedAnalysis:
        async with self.sessions() as session:
            async with session.begin():
                if self.actor_id is not None and not await AuthRepository(session).company_allowed(self.actor_id, source_id, True):
                    raise denied()
                record = await CompanyRepository(session).get_by_source_id(source_id)
                if record is None:
                    raise CompanyNotFound(source_id)
                if self.actor_id is not None and not await AuthRepository(session).news_allowed(self.actor_id, news_id):
                    raise denied()
                stored = await NewsRepository(session).get_by_id(news_id)
                if stored is None:
                    raise NewsNotFound(news_id)
                news = stored["content"]
                if not isinstance(news, str) or not news.strip() or len(news) > 100_000:
                    raise NewsNotAnalyzable(news_id)
                claim = await NewsAnalysisJobRepository(session).claim(record.id, news_id)
                if claim.cached is None:
                    company = await self._profile_for_analysis(session, record)
        if claim.cached is not None:
            try:
                cached = cached_analysis(claim.cached)
                response = cached.cached_response
                if (response.run_id != claim.run_id or response.news_id != news_id
                        or response.company_id != source_id or response.analysis.company_id != source_id
                        or response.analysis.news != news):
                    raise ValueError('Stored response does not match the pair/input')
                return cached
            except (ValueError, TypeError, KeyError) as error:
                raise AnalysisConflict('ANALYSIS_HISTORY_INVALID',claim.run_id) from error
        return await self._execute(source_id, news, record, news_id, claim.run_id, claim, company)

    async def _execute(self, source_id, news, record, news_id, run_id, claim=None, company=None) -> SavedAnalysis:
        # No session or transaction survives this boundary.
        phase = "AI_ANALYSIS_FAILED"
        try:
            if claim is not None:
                async with self.sessions() as session, session.begin():
                    await NewsAnalysisJobRepository(session).dispatch(claim)
            kwargs = dict(news=news, company=company if company is not None else to_company_profile(record))
            raw = await invoke(self.analyzer, **kwargs) if claim is not None else await self.analyzer(**kwargs)
            bundle = PersistableAnalysis.model_validate(raw)
            if bundle.analysis.company_id != source_id or bundle.analysis.news != news:
                raise ValueError("Analysis does not match its input")
            phase = "ANALYSIS_STORAGE_FAILED"
            async with self.sessions() as session:
                async with session.begin():
                    jobs = NewsAnalysisJobRepository(session)
                    if claim is not None:
                        await jobs.owner(claim)
                    insight_id = await CompanyAnalysisRepository(session).create(run_id, record.id, news_id, bundle)
                    for fragment in bundle.evidence:
                        await self.evidence_repository(session).create(insight_id, fragment)
                    if claim is not None:
                        payload = CreatedCompanyAnalysis(run_id=run_id, insight_id=insight_id,
                            news_id=news_id, company_id=source_id, analysis=bundle.analysis)
                        await jobs.save_response(claim, payload.model_dump(mode='json'))
                    await AnalysisRunRepository(session).finish(
                        run_id, "COMPLETED", model_name=bundle.model_name,
                        prompt_version=bundle.prompt_version, result_summary=bundle.analysis.summary,
                    )
            return SavedAnalysis(run_id, insight_id, news_id, bundle)
        except AnalysisConflict:
            raise
        except (Exception, asyncio.CancelledError) as error:
            # A bounded dataset adapter supplies only fixed diagnostic codes, never provider bodies.
            from services.dataset_analysis import DatasetRequestFailure
            if isinstance(error, DatasetRequestFailure):
                phase = error.code
            try:
                async with self.sessions() as session:
                    async with session.begin():
                        if claim is not None:
                            jobs = NewsAnalysisJobRepository(session)
                            row = await jobs.owner(claim, allow_completed=True)
                            if row['status'] == 'COMPLETED':
                                return cached_analysis(row['response_payload'], reused=False)
                            await jobs.require_review(claim)
                        await AnalysisRunRepository(session).finish(run_id, "FAILED", error_message=phase)
            except AnalysisConflict:
                raise
            except Exception as status_error:
                # Never claim FAILED if its transaction could not be committed.
                raise RunStatusUncertain(run_id, "RUN_STATUS_UNCERTAIN") from status_error
            if isinstance(error, asyncio.CancelledError):
                raise
            raise AnalysisFailure(run_id, phase) from error
