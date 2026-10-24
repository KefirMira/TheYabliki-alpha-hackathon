import hashlib

from sqlalchemy import insert, select, or_, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from repositories.analysis_tables import news_articles


class NewsRepository:
    def __init__(self, session):
        self.session = session

    async def create_manual(self, news: str, title: str | None = None) -> int:
        result = await self.session.execute(insert(news_articles).values(
            title=title or " ".join(news.split())[:120], content=news, input_kind="MANUAL",
            content_hash=hashlib.sha256(news.encode("utf8")).hexdigest(),
        ).returning(news_articles.c.id))
        return result.scalar_one()

    async def get_by_id(self, news_id):
        result = await self.session.execute(select(news_articles).where(news_articles.c.id == news_id))
        return result.mappings().one_or_none()

    async def get_by_url(self, url):
        result = await self.session.execute(select(news_articles).where(news_articles.c.url == url))
        return result.mappings().one_or_none()

    async def find_identities(self, incoming):
        predicates = []
        if incoming.source_name is not None and incoming.source_id is not None:
            predicates.append(and_(
                news_articles.c.input_kind == "EXTERNAL",
                news_articles.c.source_name.collate("C") == incoming.source_name,
                news_articles.c.source_id.collate("C") == incoming.source_id,
            ))
        if incoming.url is not None:
            predicates.append(news_articles.c.url == incoming.url)
        if not predicates:
            return []
        result = await self.session.execute(select(news_articles).where(or_(*predicates)))
        return list(result.mappings().all())

    async def insert_external(self, incoming):
        result = await self.session.execute(pg_insert(news_articles).values(
            **incoming.model_dump(), input_kind="EXTERNAL",
            content_hash=hashlib.sha256(incoming.content.encode("utf-8")).hexdigest(),
        ).on_conflict_do_nothing().returning(news_articles.c.id))
        return result.scalar_one_or_none()
