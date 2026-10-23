"""Catalogue drift tests only modify disposable UUID databases on the test server."""
import asyncio
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from main import app
from db.readiness import news_identity_ready, IDENTITY_OBJECTS_QUERY
from test_news_identity_migration import isolated_database, apply


@pytest.mark.parametrize("catalogue_ready", [True, False, "unavailable"])
@pytest.mark.parametrize("mode", ["demo", "full"])
def test_readiness_identity_status(monkeypatch, catalogue_ready, mode):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("AI_MODE", mode)
    monkeypatch.setattr("api.readiness.rag_ready", lambda: True)
    for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.setenv(key, "synthetic-unused")
    statements = []

    class Session:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def execute(self, statement, params):
            statements.append(str(statement))
            if "name" not in params and catalogue_ready == "unavailable":
                raise OSError("secret DSN / SQL must not leak")
            class Result:
                def scalar_one(self):
                    return "existing" if "name" in params else catalogue_ready
            return Result()

    with TestClient(app) as client:
        app.state.company_sessions = Session
        response = client.get("/ready")
    assert response.status_code == (200 if catalogue_ready is True else 503)
    assert response.json() == {"status": "ready" if catalogue_ready is True else "not_ready",
        "checks": {"rag": True, "llm_config": True, "database": catalogue_ready is True}}
    assert "secret" not in response.text
    assert statements[-1] == str(IDENTITY_OBJECTS_QUERY)
    assert all(statement.lstrip().startswith("SELECT") for statement in statements)


@pytest.mark.integration
@pytest.mark.parametrize("mutation", [
    "none", "before_004", "missing_name", "missing_id", "unvalidated",
    "wrong_check", "missing_index", "nonunique", "wrong_predicate", "wrong_collation",
    "wrong_order", "wrong_table", "index_name_is_table",
])
def test_catalogue_on_postgresql(mutation):
    dsn = os.environ.get("NEWS_IDENTITY_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Requires isolated PostgreSQL via run-profile-tests.ps1")

    async def scenario():
        async with isolated_database(dsn.replace("postgresql+asyncpg://", "postgresql://", 1)) as (connection, name):
            if mutation != "before_004":
                await apply(connection)
            changes = {
                "missing_name": "ALTER TABLE news_articles DROP CONSTRAINT news_external_source_name_check",
                "missing_id": "ALTER TABLE news_articles DROP CONSTRAINT news_external_source_id_check",
                "unvalidated": "ALTER TABLE news_articles DROP CONSTRAINT news_external_source_id_check; ALTER TABLE news_articles ADD CONSTRAINT news_external_source_id_check CHECK (input_kind<>'EXTERNAL' OR source_id IS NULL OR (source_id<>'' AND source_id COLLATE \"C\" !~ '^[[:space:]]|[[:space:]]$')) NOT VALID",
                "wrong_check": "ALTER TABLE news_articles DROP CONSTRAINT news_external_source_name_check; ALTER TABLE news_articles ADD CONSTRAINT news_external_source_name_check CHECK (source_name IS NULL)",
                "missing_index": "DROP INDEX uq_news_external_source_identity",
                "nonunique": 'DROP INDEX uq_news_external_source_identity; CREATE INDEX uq_news_external_source_identity ON news_articles (source_name COLLATE "C", source_id COLLATE "C") WHERE input_kind=\'EXTERNAL\' AND source_name IS NOT NULL AND source_id IS NOT NULL AND btrim(source_name)<>\'\' AND btrim(source_id)<>\'\'',
                "wrong_predicate": 'DROP INDEX uq_news_external_source_identity; CREATE UNIQUE INDEX uq_news_external_source_identity ON news_articles (source_name COLLATE "C", source_id COLLATE "C") WHERE input_kind=\'MANUAL\' AND source_name IS NOT NULL AND source_id IS NOT NULL AND btrim(source_name)<>\'\' AND btrim(source_id)<>\'\'',
                "wrong_collation": 'DROP INDEX uq_news_external_source_identity; CREATE UNIQUE INDEX uq_news_external_source_identity ON news_articles (source_name COLLATE "POSIX", source_id COLLATE "POSIX") WHERE input_kind=\'EXTERNAL\' AND source_name IS NOT NULL AND source_id IS NOT NULL AND btrim(source_name)<>\'\' AND btrim(source_id)<>\'\'',
                "wrong_order": 'DROP INDEX uq_news_external_source_identity; CREATE UNIQUE INDEX uq_news_external_source_identity ON news_articles (source_id COLLATE "C", source_name COLLATE "C") WHERE input_kind=\'EXTERNAL\' AND source_name IS NOT NULL AND source_id IS NOT NULL AND btrim(source_name)<>\'\' AND btrim(source_id)<>\'\'',
                "wrong_table": "DROP INDEX uq_news_external_source_identity; CREATE UNIQUE INDEX uq_news_external_source_identity ON companies (source_id)",
                "index_name_is_table": "DROP INDEX uq_news_external_source_identity; CREATE TABLE uq_news_external_source_identity (id int)",
            }
            if mutation in changes:
                await connection.execute(changes[mutation])
            url = make_url(dsn).set(drivername="postgresql+asyncpg", database=name)
            engine = create_async_engine(url)
            try:
                async with async_sessionmaker(engine)() as session:
                    # Read-only transaction proves the production probe cannot execute DDL/DML.
                    from sqlalchemy import text
                    await session.execute(text("SET TRANSACTION READ ONLY"))
                    assert await news_identity_ready(session) is (mutation == "none")
                    await session.rollback()
                if mutation == "none":
                    await apply(connection)  # Migration replay and readiness agree.
                    async with async_sessionmaker(engine)() as session:
                        assert await news_identity_ready(session)
            finally:
                await engine.dispose()
    asyncio.run(scenario())


def test_catalogue_checks_all_index_state_flags():
    query = str(IDENTITY_OBJECTS_QUERY)
    for flag in ("indisunique", "indisvalid", "indisready", "indislive"):
        assert "AND i." + flag in query
