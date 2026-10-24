from api.auth import current_actor, AUTH_ERRORS
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import SQLAlchemyError

from db.session import get_session_factory, unavailable
from schemas.news import ExternalNewsInput, IngestedNews
from schemas.http_docs import APIError
from services.news_ingestion_service import NewsIdentityConflict, NewsIngestionRetry, NewsIngestionService
from settings import execution_mode

router = APIRouter(prefix="/api/news", tags=["news ingestion"], dependencies=[Depends(current_actor)], responses=AUTH_ERRORS)


def get_news_service(sessions=Depends(get_session_factory), actor=Depends(current_actor)):
    return NewsIngestionService(sessions, actor_id=actor.user_id)


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
    403: {"model": APIError, "description": "Demo synthetic data policy rejected the input"},
    409: {"model": APIError, "description": "Pair and URL identify different stored news"},
    503: {"model": APIError, "description": "Database unavailable or bounded concurrency retry required"},
}, description="EXTERNAL без AI. Обязательны title/content (до 500/100000). Пара source_name+source_id — основной ключ, канонический HTTP(S) URL — дополнительный. Без идентификаторов дедупликации нет. Дубликат не перезаписывается; даты с timezone. Demo: synthetic-demo / SYNTH-* / example.invalid.")
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
