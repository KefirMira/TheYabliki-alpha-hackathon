from repositories.company_repository import CompanyRepository
from repositories.insight_repository import InsightRepository
from schemas.insights import InsightCard, InsightFeed, InsightFeedItem, InsightNews
from services.company_profile_service import CompanyNotFound
from services.insight_cursor import InvalidInsightCursor, encode_cursor


class InsightNotFound(Exception):
    pass


class InsightService:
    def __init__(self, session):
        self.companies = CompanyRepository(session)
        self.insights = InsightRepository(session)

    async def company(self, source_id):
        record = await self.companies.get_by_source_id(source_id)
        if record is None:
            raise CompanyNotFound(source_id)
        return record

    async def list(self, source_id, limit, position=None):
        if position is not None and position.company_id != source_id:
            raise InvalidInsightCursor("Cursor belongs to another company")
        record = await self.company(source_id)
        rows = await self.insights.list_completed(record.id, limit, position)
        visible = rows[:limit]
        next_cursor = None
        if len(rows) > limit:
            last = visible[-1]
            next_cursor = encode_cursor(source_id, last["created_at"], last["insight_id"])
        return InsightFeed(
            items=[InsightFeedItem(company_id=source_id, **row) for row in visible],
            next_cursor=next_cursor,
        )

    async def card(self, source_id, insight_id):
        record = await self.company(source_id)
        row = await self.insights.get_completed(record.id, insight_id)
        if row is None:
            raise InsightNotFound(insight_id)
        evidence = await self.insights.get_evidence(record.id, insight_id)
        return InsightCard(
            company_id=source_id, **{key: row[key] for key in (
                "insight_id", "run_id", "type", "relevance", "summary", "created_at", "status",
                "risks", "opportunities", "recommendations", "validation",
            )},
            news=InsightNews(id=row["news_id"], title=row["news_title"], text=row["news_text"]),
            sources=row["source_snapshot"], evidence=evidence,
        )
