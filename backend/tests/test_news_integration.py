import asyncio
import hashlib

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from api.news import get_news_service
from main import app
from repositories.news_repository import NewsRepository
from schemas.news import ExternalNewsInput
from services.news_ingestion_service import NewsIngestionService

pytestmark = pytest.mark.integration


@pytest.fixture
def news_database(test_database_url, monkeypatch):
    monkeypatch.setenv("AI_MODE", "full")
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def baseline():
        async with engine.connect() as connection:
            # Fail before writes unless the isolated database actually applied 004.
            assert await connection.scalar(text("""
                SELECT indisunique AND indisvalid AND
                  indcollation[0]='pg_catalog."C"'::regcollation AND
                  indcollation[1]='pg_catalog."C"'::regcollation
                FROM pg_index WHERE indexrelid=to_regclass('public.uq_news_external_source_identity')
            """))
            ids = list((await connection.execute(text("SELECT id FROM news_articles"))).scalars())
            runs = await connection.scalar(text("SELECT count(*) FROM analysis_runs"))
            return ids, runs

    ids, runs = asyncio.run(baseline())
    service = NewsIngestionService(sessions)
    app.dependency_overrides[get_news_service] = lambda: service
    yield engine, sessions, service
    app.dependency_overrides.pop(get_news_service, None)

    async def cleanup():
        try:
            async with engine.begin() as connection:
                assert await connection.scalar(text("SELECT count(*) FROM analysis_runs")) == runs
                from repositories.analysis_tables import news_articles
                await connection.execute(news_articles.delete().where(news_articles.c.id.not_in(ids)))
        finally:
            await engine.dispose()
    asyncio.run(cleanup())


def news(**changes):
    return ExternalNewsInput(title="Synthetic parser title", content="Synthetic parser content", **changes)


async def request(payload):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.post("/api/news", json=payload)


def test_create_persists_metadata_without_analysis(news_database):
    _, sessions, service = news_database
    async def scenario():
        incoming = news(url="HTTPS://EXAMPLE.INVALID/Article?utm_campaign=demo&id=7#fragment",
                        source_name="wire.test", source_id="Case-A", published_at="2026-01-01T12:00:00+03:00", language="ru")
        created = await service.ingest(incoming)
        assert created.created and not created.duplicate and created.diagnostics == []
        async with sessions() as session:
            repository = NewsRepository(session)
            stored = await repository.get_by_id(created.news_id)
            assert stored["input_kind"] == "EXTERNAL"
            assert stored["url"] == "https://example.invalid/Article?id=7"
            assert stored["content_hash"] == hashlib.sha256(incoming.content.encode()).hexdigest()
            assert stored["published_at"] == incoming.published_at
            assert (await repository.get_by_url(stored["url"]))["id"] == created.news_id
    asyncio.run(scenario())


def test_changed_duplicate_never_rewrites_record(news_database):
    _, sessions, service = news_database
    async def scenario():
        original = news(source_name="wire", source_id="A", url="https://example.invalid/first", language="ru")
        first = await service.ingest(original)
        changed = original.model_copy(update={"content": "Changed synthetic text", "title": "Changed title",
                                              "url": "https://example.invalid/second", "language": "en"})
        duplicate = await service.ingest(changed)
        assert duplicate.news_id == first.news_id and duplicate.duplicate and not duplicate.created
        assert set(duplicate.diagnostics) == {"CONTENT_MISMATCH", "TITLE_MISMATCH", "URL_MISMATCH", "METADATA_MISMATCH"}
        async with sessions() as session:
            stored = await NewsRepository(session).get_by_id(first.news_id)
            assert stored["content"] == original.content and stored["url"] == original.url and stored["language"] == "ru"
    asyncio.run(scenario())


def test_url_duplicate_with_other_external_id(news_database):
    _, _, service = news_database
    async def scenario():
        first = await service.ingest(news(source_name="wire", source_id="A", url="https://example.invalid/a?utm_source=x&id=1"))
        duplicate = await service.ingest(news(source_name="other", source_id="B", url="https://example.invalid/a?id=1&fbclid=y#part"))
        assert duplicate.news_id == first.news_id and duplicate.duplicate
        assert duplicate.diagnostics == ["SOURCE_IDENTITY_MISMATCH"]
        assert duplicate.news.source_name == "wire" and duplicate.news.source_id == "A"
    asyncio.run(scenario())


def test_http_two_identities_conflict(news_database):
    engine, _, service = news_database
    async def scenario():
        await service.ingest(news(source_name="wire", source_id="A", url="https://example.invalid/a"))
        await service.ingest(news(source_name="wire", source_id="B", url="https://example.invalid/b"))
        async with engine.connect() as connection:
            before = await connection.scalar(text("SELECT jsonb_agg(to_jsonb(n) ORDER BY id)::text FROM news_articles n"))
        response = await request(news(source_name="wire", source_id="A", url="https://example.invalid/b").model_dump(mode="json"))
        assert response.status_code == 409 and response.json()["detail"]["code"] == "NEWS_IDENTITY_CONFLICT"
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT jsonb_agg(to_jsonb(n) ORDER BY id)::text FROM news_articles n")) == before
    asyncio.run(scenario())


@pytest.mark.parametrize("identity,duplicate", [
    ({}, False), ({"source_name": "wire"}, False), ({"source_id": "A"}, False),
    ({"source_name": "wire", "source_id": "A"}, True),
])
def test_no_url_identity_policy(news_database, identity, duplicate):
    _, _, service = news_database
    async def scenario():
        first = await service.ingest(news(**identity))
        second = await service.ingest(news(**identity))
        assert second.duplicate is duplicate
        assert (first.news_id == second.news_id) is duplicate
    asyncio.run(scenario())


def test_same_text_distinct_publications(news_database):
    _, _, service = news_database
    async def scenario():
        results = [await service.ingest(news(url=url)) for url in (
            "http://example.invalid/Article", "https://example.invalid/Article", "https://example.invalid/article")]
        assert len({item.news_id for item in results}) == 3
    asyncio.run(scenario())


@pytest.mark.parametrize("race", ["both", "pair", "url"])
def test_concurrent_http_insert_rereads_after_conflict(news_database, monkeypatch, race):
    engine, _, _ = news_database
    original = NewsRepository.find_identities
    inserted = NewsRepository.insert_external
    async def scenario():
        barrier = asyncio.Barrier(8)
        calls = {"find": 0, "insert": 0}
        async def find(self, incoming):
            result = await original(self, incoming)
            calls["find"] += 1
            if not getattr(self, "initial_read_done", False):
                self.initial_read_done = True
                assert result == []
                await asyncio.wait_for(barrier.wait(), timeout=15)
            return result
        async def insert(self, incoming):
            calls["insert"] += 1
            return await inserted(self, incoming)
        monkeypatch.setattr(NewsRepository, "find_identities", find)
        monkeypatch.setattr(NewsRepository, "insert_external", insert)
        incoming = news(source_name="wire", source_id="parallel", url="https://example.invalid/parallel").model_dump(mode="json")
        requests = []
        for index in range(8):
            current = dict(incoming)
            if race == "pair":
                current["url"] += f"/{index}"
            if race == "url":
                current["source_id"] += f"-{index}"
            requests.append(request(current))
        results = await asyncio.wait_for(asyncio.gather(*requests), timeout=30)
        assert [item.status_code for item in results].count(201) == 1
        assert [item.status_code for item in results].count(200) == 7
        assert len({item.json()["news_id"] for item in results}) == 1
        assert calls == {"find": 15, "insert": 8}
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT count(*) FROM news_articles WHERE source_name='wire' AND source_id LIKE 'parallel%'")) == 1
    asyncio.run(scenario())
