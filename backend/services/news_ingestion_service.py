from repositories.auth_repository import AuthRepository
from services.auth_service import denied
from schemas.news import IngestedNews, NewsMetadata
from repositories.news_repository import NewsRepository


class NewsIdentityConflict(Exception):
    pass


class NewsIngestionRetry(Exception):
    pass


def duplicate_result(rows, incoming):
    if len(rows) > 1:
        raise NewsIdentityConflict()
    stored = rows[0]
    diagnostics = []
    if incoming.url is not None and incoming.url != stored["url"]:
        diagnostics.append("URL_MISMATCH")
    if (incoming.source_name is not None or incoming.source_id is not None) and (
        stored["input_kind"] != "EXTERNAL" or any(
            getattr(incoming, field) is not None and getattr(incoming, field) != stored[field]
            for field in ("source_name", "source_id"))
    ):
        diagnostics.append("SOURCE_IDENTITY_MISMATCH")
    if incoming.content != stored["content"]:
        diagnostics.append("CONTENT_MISMATCH")
    if incoming.title != stored["title"]:
        diagnostics.append("TITLE_MISMATCH")
    if any(getattr(incoming, field) is not None and getattr(incoming, field) != stored[field]
           for field in ("published_at", "language")):
        diagnostics.append("METADATA_MISMATCH")
    return IngestedNews(news_id=stored["id"], created=False, duplicate=True,
                        diagnostics=diagnostics, news=NewsMetadata.model_validate(stored))


class NewsIngestionService:
    def __init__(self, sessions, actor_id=None):
        self.sessions = sessions
        self.actor_id = actor_id

    async def ingest(self, incoming):
        async with self.sessions() as session:
            async with session.begin():
                repository = NewsRepository(session)
                rows = await repository.find_identities(incoming)
                if rows:
                    if self.actor_id is not None:
                        for row in rows:
                            if not await AuthRepository(session).news_allowed(self.actor_id, row['id']):
                                raise denied()
                    return duplicate_result(rows, incoming)
                news_id = await repository.insert_external(incoming)
                if news_id is not None:
                    if self.actor_id is not None:
                        await AuthRepository(session).grant_news(self.actor_id, news_id)
                    stored = await repository.get_by_id(news_id)
                    return IngestedNews(news_id=news_id, created=True, duplicate=False,
                                        diagnostics=[], news=NewsMetadata.model_validate(stored))
                # A new READ COMMITTED statement sees the concurrent committed row.
                rows = await repository.find_identities(incoming)
                if rows:
                    if self.actor_id is not None:
                        for row in rows:
                            if not await AuthRepository(session).news_allowed(self.actor_id, row['id']):
                                raise denied()
                    return duplicate_result(rows, incoming)
                raise NewsIngestionRetry()  # One INSERT and one re-read, never an unbounded loop.
