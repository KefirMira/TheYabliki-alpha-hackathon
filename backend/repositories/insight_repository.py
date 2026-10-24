from sqlalchemy import BigInteger, DateTime, String, and_, column, or_, select, table, tuple_
from sqlalchemy.dialects.postgresql import JSONB

from repositories.analysis_tables import analysis_runs, insight_evidence, news_articles


# Read projection only. Existing persistence projections and SQL stay unchanged.
insights = table(
    "company_news_analyses", column("id", BigInteger), column("company_id", BigInteger),
    column("analysis_run_id", BigInteger), column("news_id", BigInteger), column("insight_kind", String),
    column("relevance_level", String), column("impact_summary", String), column("created_at", DateTime(timezone=True)),
    *[column(name, JSONB) for name in ("risks", "opportunities", "recommendations", "validation", "source_snapshot")],
    schema="public",
)


def completed_scope(company_id):
    return and_(
        insights.c.company_id == company_id,
        analysis_runs.c.status == "COMPLETED",
        or_(analysis_runs.c.company_id.is_(None), analysis_runs.c.company_id == company_id),
    )


def feed_columns():
    return (
        insights.c.id.label("insight_id"), insights.c.analysis_run_id.label("run_id"),
        insights.c.insight_kind.label("type"), insights.c.relevance_level.label("relevance"),
        insights.c.impact_summary.label("summary"), insights.c.created_at,
        analysis_runs.c.status,
    )


class InsightRepository:
    def __init__(self, session):
        self.session = session

    async def list_completed(self, company_id, limit, position=None):
        query = select(*feed_columns()).select_from(
            insights.join(analysis_runs, insights.c.analysis_run_id == analysis_runs.c.id)
        ).where(completed_scope(company_id))
        if position is not None:
            query = query.where(tuple_(insights.c.created_at, insights.c.id) < tuple_(position.created_at, position.id))
        query = query.order_by(insights.c.created_at.desc(), insights.c.id.desc()).limit(limit + 1)
        result = await self.session.execute(query)
        return list(result.mappings().all())

    async def get_completed(self, company_id, insight_id):
        result = await self.session.execute(select(
            *feed_columns(), insights.c.news_id, insights.c.risks, insights.c.opportunities,
            insights.c.recommendations, insights.c.validation, insights.c.source_snapshot,
            news_articles.c.title.label("news_title"), news_articles.c.content.label("news_text"),
        ).select_from(
            insights.join(analysis_runs, insights.c.analysis_run_id == analysis_runs.c.id)
            .join(news_articles, insights.c.news_id == news_articles.c.id)
        ).where(completed_scope(company_id), insights.c.id == insight_id))
        return result.mappings().one_or_none()

    async def get_evidence(self, company_id, insight_id):
        result = await self.session.execute(select(
            insight_evidence.c.id, insight_evidence.c.evidence_type,
            insight_evidence.c.evidence_text.label("text"), insight_evidence.c.document_name.label("document"),
            insight_evidence.c.document_page.label("page"), insight_evidence.c.chunk_id,
            insight_evidence.c.document_date,
        ).select_from(
            insight_evidence.join(insights, insight_evidence.c.company_news_analysis_id == insights.c.id)
            .join(analysis_runs, insights.c.analysis_run_id == analysis_runs.c.id)
        ).where(completed_scope(company_id), insights.c.id == insight_id).order_by(insight_evidence.c.id))
        return list(result.mappings().all())
