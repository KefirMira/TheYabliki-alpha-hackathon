"""Single-news, atomic, repeatable matching. No AI imports or analysis writes."""
from repositories.news_match_repository import NewsMatchRepository
from services.company_news_matcher import ALGORITHM_VERSION, digest, match_news


class NewsMatchingService:
    def __init__(self, sessions):
        self.sessions = sessions

    async def match(self, news_id):
        async with self.sessions() as session, session.begin():
            repository = NewsMatchRepository(session)
            # Serializes only this news. All reads/writes finish in one transaction.
            news = await repository.lock_news(news_id)
            snapshot = {key: news[key] for key in ('title', 'content')}
            catalogue = await repository.catalogue()
            nh, dh = digest(snapshot), digest(catalogue)
            run_id = await repository.find(news_id, ALGORITHM_VERSION, nh, dh)
            reused = run_id is not None
            if not reused:
                result = match_news(snapshot, catalogue)
                run_id = await repository.save(news_id, ALGORITHM_VERSION, nh, dh, snapshot, result)
            response = await repository.get(news_id, run_id)
        return {**response, 'reused': reused}

    async def show(self, news_id, run_id=None):
        async with self.sessions() as session, session.begin():
            return await NewsMatchRepository(session).get(news_id, run_id)
