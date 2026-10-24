from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.news import get_news_service
from main import app
from schemas.news import ExternalNewsInput, IngestedNews
from services.news_ingestion_service import NewsIdentityConflict, NewsIngestionRetry


def payload(**changes):
    return {"title": "Synthetic title", "content": "Synthetic text", **changes}


@pytest.mark.parametrize("url,expected", [
    ("HTTPS://EXAMPLE.INVALID/News/AbC?utm_source=x&article=1&fbclid=x#part", "https://example.invalid/News/AbC?article=1"),
    ("http://example.invalid/A?x=2&x=1&gclid=a&encoded=%2f", "http://example.invalid/A?x=2&x=1&encoded=%2f"),
    ("https://example.invalid/A?%75tm_medium=x&ref=keep", "https://example.invalid/A?ref=keep"),
    ("https://example.invalid:443/A/", "https://example.invalid:443/A/"),
])
def test_conservative_url(url, expected):
    assert ExternalNewsInput(**payload(url=url)).url == expected


@pytest.mark.parametrize("changes", [
    {"title": " "}, {"content": "\n "}, {"content": "x" * 100001}, {"title": "x" * 501},
    {"url": "ftp://example.invalid/a"}, {"url": "http:///path"}, {"url": "https://a b.invalid"},
    {"url": "https://user:pass@example.invalid"}, {"url": "https://example.invalid/%zz"},
    {"source_name": "UPPER"}, {"source_name": "with space"}, {"source_name": "источник"}, {"source_name": "wire\n"},
    {"source_id": " padded"}, {"source_id": "id\t"}, {"source_id": ""},
    {"published_at": "2026-01-01T12:00:00"}, {"published_at": 1234567890},
    {"language": "x" * 11}, {"content": "abc\x00"}, {"source_id": "a\x00b"},
])
def test_invalid_input(changes):
    with pytest.raises(ValidationError):
        ExternalNewsInput(**payload(**changes))


def test_optional_metadata_and_timezone():
    incoming = ExternalNewsInput(**payload(published_at="2026-01-01T12:00:00+03:00", source_id="CaseSensitive"))
    assert incoming.published_at.utcoffset().total_seconds() == 10800
    assert incoming.source_name is None and incoming.source_id == "CaseSensitive"


@pytest.fixture
def news_api(monkeypatch):
    monkeypatch.setenv("AI_MODE", "full")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    service = AsyncMock()
    app.dependency_overrides[get_news_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_news_service, None)


@pytest.mark.parametrize("created,status", [(True, 201), (False, 200)])
def test_api_success_without_sdk(news_api, created, status):
    news_api.ingest.return_value = IngestedNews(news_id=7, created=created, duplicate=not created, diagnostics=[],
        news={"title": "Stored", "url": None, "source_name": None, "source_id": None,
              "published_at": None, "language": None, "input_kind": "EXTERNAL"})
    with TestClient(app) as client:
        response = client.post("/api/news", json=payload())
    assert response.status_code == status and response.json()["created"] is created
    news_api.ingest.assert_awaited_once()


@pytest.mark.parametrize("error,status,code", [
    (NewsIdentityConflict(), 409, "NEWS_IDENTITY_CONFLICT"),
    (NewsIngestionRetry(), 503, "NEWS_INGESTION_RETRY"),
    (OSError("private connection data"), 503, "DATABASE_UNAVAILABLE"),
])
def test_api_errors(news_api, error, status, code):
    news_api.ingest.side_effect = error
    with TestClient(app) as client:
        response = client.post("/api/news", json=payload())
    assert response.status_code == status and response.json()["detail"]["code"] == code
    assert "private" not in response.text


def test_api_validation_before_storage(news_api):
    with TestClient(app) as client:
        assert client.post("/api/news", json=payload(published_at="2026-01-01")).status_code == 422
    news_api.ingest.assert_not_awaited()


@pytest.mark.parametrize("changes,accepted", [
    ({}, False),
    ({"source_name": "synthetic-demo", "source_id": "SYNTH-A"}, True),
    ({"source_name": "synthetic-demo", "source_id": "SYNTH-A", "url": "https://example.invalid/a"}, True),
    ({"source_name": "synthetic-demo", "source_id": "SYNTH-A", "url": "https://real.example.com/a"}, False),
])
def test_demo_policy(news_api, monkeypatch, changes, accepted):
    monkeypatch.setenv("AI_MODE", "demo")
    news_api.ingest.return_value = IngestedNews(news_id=1, created=True, duplicate=False, diagnostics=[],
        news={"title": "Synthetic", "url": None, "source_name": "synthetic-demo", "source_id": "SYNTH-A",
              "published_at": None, "language": None, "input_kind": "EXTERNAL"})
    with TestClient(app) as client:
        response = client.post("/api/news", json=payload(**changes))
    assert response.status_code == (201 if accepted else 403)
    if not accepted:
        news_api.ingest.assert_not_awaited()


def test_api_database_absent(monkeypatch):
    monkeypatch.setenv("AI_MODE", "full")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app) as client:
        response = client.post("/api/news", json=payload())
    assert response.status_code == 503


@pytest.mark.parametrize("found", [True, False])
def test_conflict_reread_is_bounded(monkeypatch, found):
    from contextlib import asynccontextmanager
    from services.news_ingestion_service import NewsIngestionService

    incoming = ExternalNewsInput(**payload(url="https://example.invalid/a"))
    stored = {**incoming.model_dump(), "id": 9, "input_kind": "EXTERNAL"}
    repository = AsyncMock()
    repository.find_identities.side_effect = [[], [stored] if found else []]
    repository.insert_external.return_value = None
    monkeypatch.setattr("services.news_ingestion_service.NewsRepository", lambda session: repository)

    @asynccontextmanager
    async def transaction():
        yield

    class Session:
        begin = staticmethod(transaction)

    @asynccontextmanager
    async def sessions():
        yield Session()

    import asyncio
    if found:
        result = asyncio.run(NewsIngestionService(sessions).ingest(incoming))
        assert result.news_id == 9 and result.duplicate
    else:
        with pytest.raises(NewsIngestionRetry):
            asyncio.run(NewsIngestionService(sessions).ingest(incoming))
    assert repository.find_identities.await_count == 2
    repository.insert_external.assert_awaited_once()
