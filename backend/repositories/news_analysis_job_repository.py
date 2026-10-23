"""All state transitions lock the pair row first. No locks survive an AI call."""
from dataclasses import dataclass
import json
from uuid import UUID, uuid4

from sqlalchemy import text

from repositories.analysis_run_repository import AnalysisRunRepository


class AnalysisConflict(Exception):
    def __init__(self, code, run_id=None):
        self.code, self.run_id = code, run_id
        super().__init__(code)


@dataclass(frozen=True)
class AnalysisClaim:
    job_id: int
    run_id: int
    token: UUID
    cached: dict | None = None


class NewsAnalysisJobRepository:
    def __init__(self, session):
        self.session = session

    async def lock_pair(self, company_id, news_id):
        await self.session.execute(text("SET LOCAL lock_timeout = '5s'"))
        await self.session.execute(text("""INSERT INTO public.news_analysis_jobs(company_id,news_id)
            VALUES (:company,:news) ON CONFLICT (company_id,news_id) DO NOTHING"""),
            {"company": company_id, "news": news_id})
        result = await self.session.execute(text("""SELECT * FROM public.news_analysis_jobs
            WHERE company_id=:company AND news_id=:news FOR UPDATE"""),
            {"company": company_id, "news": news_id})
        return result.mappings().one()

    async def latest(self, job_id):
        result = await self.session.execute(text("""SELECT a.*,r.status,
            a.deadline_at <= clock_timestamp() AS expired,
            (a.retry_not_before IS NULL OR a.retry_not_before <= clock_timestamp()) AS retry_due
            FROM public.news_analysis_attempts a JOIN public.analysis_runs r ON r.id=a.run_id
            WHERE a.job_id=:job ORDER BY a.attempt_no DESC LIMIT 1"""), {"job": job_id})
        return result.mappings().one_or_none()

    async def claim(self, company_id, news_id, lease_seconds=180):
        job = await self.lock_pair(company_id, news_id)
        previous = await self.latest(job['id'])
        if previous:
            if previous['status'] == 'COMPLETED':
                if not previous['response_payload'] or previous['insight_id'] is None:
                    raise AnalysisConflict('ANALYSIS_HISTORY_INVALID', previous['run_id'])
                return AnalysisClaim(job['id'], previous['run_id'], previous['claim_token'], previous['response_payload'])
            if previous['status'] == 'RUNNING':
                code = 'ANALYSIS_REVIEW_REQUIRED' if previous['expired'] else 'ANALYSIS_ALREADY_RUNNING'
                raise AnalysisConflict(code, previous['run_id'])
            if previous['attempt_no'] >= job['max_attempts']:
                raise AnalysisConflict('ANALYSIS_ATTEMPT_LIMIT_REACHED', previous['run_id'])
            if previous['status'] != 'FAILED' or previous['retry_policy'] not in ('SAFE','MANUAL_APPROVED') or not previous['retry_due']:
                raise AnalysisConflict('ANALYSIS_RETRY_REQUIRED', previous['run_id'])
        else:
            # Until legacy registration validates the payload, fail closed.
            legacy = await self.session.scalar(text("""SELECT EXISTS(SELECT 1 FROM public.company_news_analyses
                WHERE company_id=:company AND news_id=:news)"""), {"company": company_id, "news": news_id})
            if legacy:
                raise AnalysisConflict('ANALYSIS_HISTORY_REVIEW_REQUIRED')
        run_id = await AnalysisRunRepository(self.session).start(company_id)
        token = uuid4()
        await self.session.execute(text("""INSERT INTO public.news_analysis_attempts
            (job_id,attempt_no,company_id,news_id,run_id,claim_token,deadline_at)
            VALUES (:job,:attempt,:company,:news,:run,:token,
                CURRENT_TIMESTAMP + CAST(:lease AS double precision) * interval '1 second')"""),
            {"job":job['id'], "attempt": previous['attempt_no']+1 if previous else 1,
             "company":company_id,"news":news_id,"run":run_id,"token":token,"lease":lease_seconds})
        return AnalysisClaim(job['id'], run_id, token)

    async def owner(self, claim, allow_completed=False):
        await self.session.execute(text("SET LOCAL lock_timeout = '5s'"))
        await self.session.execute(text("SELECT id FROM public.news_analysis_jobs WHERE id=:job FOR UPDATE"), {'job':claim.job_id})
        row = await self.latest(claim.job_id)
        if not row or row['run_id'] != claim.run_id or row['claim_token'] != claim.token:
            raise AnalysisConflict('ANALYSIS_ATTEMPT_CLOSED', claim.run_id)
        if row['status'] != 'RUNNING' and not (allow_completed and row['status']=='COMPLETED'):
            raise AnalysisConflict('ANALYSIS_ATTEMPT_CLOSED', claim.run_id)
        return row

    async def dispatch(self, claim):
        row = await self.owner(claim)
        if row['dispatch_started_at'] is not None:
            raise AnalysisConflict('ANALYSIS_ALREADY_DISPATCHED', claim.run_id)
        await self.session.execute(text("""UPDATE public.news_analysis_attempts
            SET dispatch_started_at=clock_timestamp() WHERE run_id=:run"""), {'run':claim.run_id})

    async def save_response(self, claim, payload):
        await self.session.execute(text("""UPDATE public.news_analysis_attempts
            SET insight_id=:insight,response_payload=CAST(:payload AS jsonb) WHERE run_id=:run"""),
            {'run':claim.run_id,'insight':payload['insight_id'],'payload':json.dumps(payload,ensure_ascii=False)})

    async def require_review(self, claim):
        await self.session.execute(text("""UPDATE public.news_analysis_attempts
            SET retry_policy='REVIEW_REQUIRED' WHERE run_id=:run"""), {'run':claim.run_id})

    async def inspect_stalled(self):
        result = await self.session.execute(text("""SELECT j.id AS job_id,j.company_id,j.news_id,
            a.run_id,a.attempt_no,a.deadline_at,a.dispatch_started_at,a.retry_policy,r.status
            FROM public.news_analysis_jobs j JOIN public.news_analysis_attempts a ON a.job_id=j.id
            JOIN public.analysis_runs r ON r.id=a.run_id
            WHERE r.status='RUNNING' AND a.deadline_at<=clock_timestamp()
            ORDER BY a.deadline_at,a.run_id LIMIT 100"""))
        return [dict(row) for row in result.mappings()]

    async def administer(self, company_id, news_id, expected_run_id, action, actor, reason,
                         worker_stopped=False, provider_finished=False):
        if not actor.strip() or not reason.strip() or not worker_stopped or not provider_finished:
            raise AnalysisConflict('ANALYSIS_ADMIN_ATTESTATION_REQUIRED', expected_run_id)
        # Never create a new job as an administrative side effect.
        result = await self.session.execute(text("""SELECT * FROM public.news_analysis_jobs
            WHERE company_id=:company AND news_id=:news FOR UPDATE"""),
            {'company':company_id,'news':news_id})
        job = result.mappings().one_or_none()
        row = await self.latest(job['id']) if job else None
        if not row or row['run_id'] != expected_run_id:
            raise AnalysisConflict('ANALYSIS_ADMIN_STALE_RUN', expected_run_id)
        if row['status']=='COMPLETED':
            raise AnalysisConflict('ANALYSIS_ALREADY_COMPLETED', expected_run_id)
        if action=='close':
            if row['status']!='RUNNING':
                raise AnalysisConflict('ANALYSIS_ATTEMPT_CLOSED', expected_run_id)
            await AnalysisRunRepository(self.session).finish(expected_run_id,'FAILED',error_message='ADMIN_CLOSED_UNCERTAIN')
            policy='REVIEW_REQUIRED'
        elif action=='approve-retry':
            if row['attempt_no']>=job['max_attempts']:
                raise AnalysisConflict('ANALYSIS_ATTEMPT_LIMIT_REACHED', expected_run_id)
            if row['status']!='FAILED' or row['insight_id'] is not None or row['response_payload'] is not None:
                raise AnalysisConflict('ANALYSIS_REVIEW_REQUIRED', expected_run_id)
            policy='MANUAL_APPROVED'
        else:
            raise ValueError('Unsupported administration action')
        await self.session.execute(text("""UPDATE public.news_analysis_attempts SET
            retry_policy=:policy,retry_reason=:reason,retry_authorized_by=:actor,
            retry_authorized_at=clock_timestamp(),retry_not_before=clock_timestamp()
            WHERE run_id=:run"""),
            {'policy':policy,'reason':reason,'actor':actor,'run':expected_run_id})
