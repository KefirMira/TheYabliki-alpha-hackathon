import hashlib

from sqlalchemy import insert

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
