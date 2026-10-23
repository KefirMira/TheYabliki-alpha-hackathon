from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import SQLAlchemyError

from db.session import get_session_factory, unavailable
from schemas.news import ExternalNewsInput, IngestedNews
from services.news_ingestion_service import NewsIdentityConflict, NewsIngestionRetry, NewsIngestionService
from settings import execution_mode

router = APIRouter(prefix="/api/news", tags=["news ingestion"])


def get_news_service(sessions=Depends(get_session_factory)):
    return NewsIngestionService(sessions)


def demo_policy(news: ExternalNewsInput):
    if execution_mode() == "demo":
        host = urlsplit(news.url).hostname if news.url else None
        if not (news.source_name == "synthetic-demo" and news.source_id is not None
                and news.source_id.startswith("SYNTH-")
                and (host is None or host == "example.invalid" or host.endswith(".example.invalid"))):
            raise HTTPException(403, detail={"code": "DEMO_SYNTHETIC_NEWS_ONLY",
                "message": "Demo принимает только synthetic-demo / SYNTH-* и URL example.invalid."})
    return news


@router.post("", response_model=IngestedNews, status_code=201, responses={
    200: {"model": IngestedNews, "description": "Existing news, unchanged; inspect diagnostics"},
    403: {"description": "Demo synthetic data policy rejected the input"},
    409: {"description": "Pair and URL identify different stored news"},
    503: {"description": "Database unavailable or bounded concurrency retry required"},
})
async def ingest_news(response: Response, news: ExternalNewsInput = Depends(demo_policy),
                      service: NewsIngestionService = Depends(get_news_service)):
    try:
        result = await service.ingest(news)
    except NewsIdentityConflict as error:
        raise HTTPException(409, detail={"code": "NEWS_IDENTITY_CONFLICT",
            "message": "Внешняя пара и URL указывают на разные новости."}) from error
    except NewsIngestionRetry as error:
        raise HTTPException(503, detail={"code": "NEWS_INGESTION_RETRY",
            "message": "Не удалось подтвердить конкурентную запись. Повторите приём."}) from error
    except (SQLAlchemyError, OSError, TimeoutError) as error:
        raise unavailable() from error
    response.status_code = 201 if result.created else 200
    return result
