"""004 tests create disposable databases only inside the isolated test server."""
import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
DATABASE_ROOT = Path(os.environ.get("NEWS_IDENTITY_DATABASE_ROOT", ROOT / "database")).resolve()
MIGRATION = (DATABASE_ROOT / "migrations/004_news_external_identity.sql").read_text(encoding="utf-8")


@pytest.fixture
def identity_dsn():
    dsn = os.environ.get("NEWS_IDENTITY_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("004 requires run-profile-tests.ps1 with the current database checkout")
    return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


@asynccontextmanager
async def isolated_database(dsn):
    # Never alter the database supplied by the caller; it is only a control connection.
    name = "test_news_identity_" + uuid4().hex
    admin = await asyncpg.connect(dsn, timeout=5)
    connection = None
    created = False
    try:
        await admin.execute(f'CREATE DATABASE "{name}"')
        created = True
        connection = await asyncpg.connect(dsn, database=name, timeout=5)
        for filename in ("schema.sql", "migrations/002_pulse_features.sql", "migrations/003_integrity.sql"):
            await connection.execute((DATABASE_ROOT / filename).read_text(encoding="utf-8-sig"))
        yield connection, name
    finally:
        if connection is not None:
            await connection.close()
        try:
            # Drop only the UUID database created in this test, never another database/volume.
            if created:
                await admin.execute(f'DROP DATABASE "{name}"')
        finally:
            await admin.close()


async def apply(connection):
    try:
        await connection.execute(MIGRATION)
    except Exception:
        await connection.execute("ROLLBACK")
        raise


async def insert(connection, source="wire.test", source_id="Item-A", kind="EXTERNAL", url=None):
    return await connection.fetchval("""
        INSERT INTO public.news_articles(title,content,input_kind,source_name,source_id,url)
        VALUES ('Synthetic migration news','Entirely invented test text',$1,$2,$3,$4) RETURNING id
    """, kind, source, source_id, url)


async def rows(connection):
    return await connection.fetchval("SELECT coalesce(jsonb_agg(to_jsonb(n) ORDER BY id),'[]')::text FROM public.news_articles n")


async def foreign_keys(connection):
    return await connection.fetchval("""
        SELECT jsonb_agg(pg_get_constraintdef(oid) ORDER BY conrelid::regclass::text, conname)::text
        FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace
    """)


def test_replay_preserves_rows_and_all_tables(identity_dsn):
    async def scenario():
        async with isolated_database(identity_dsn) as (connection, _):
            await insert(connection)
            await insert(connection, source_id="Item-B", url="https://example.invalid/b")
            await insert(connection, source="AN OLD MANUAL SOURCE", source_id=" padded ", kind="MANUAL")
            before = await rows(connection)
            before_keys = await foreign_keys(connection)
            preflight = (ROOT / "database/tests/news_identity_preflight.sql").read_text(encoding="utf-8")
            await connection.execute(preflight)
            for _ in range(2):
                await apply(connection)
                await connection.execute(preflight)
                assert await rows(connection) == before
                assert await foreign_keys(connection) == before_keys
            assert await connection.fetchval("SELECT count(*) FROM pg_tables WHERE schemaname='public'") == 13
            assert await connection.fetchval("SELECT count(*) FROM pg_indexes WHERE schemaname='public' AND indexname='uq_news_external_source_identity'") == 1
            collations = await connection.fetch("""
                SELECT c.collname FROM pg_index i
                CROSS JOIN LATERAL unnest(i.indcollation::oid[]) WITH ORDINALITY v(oid, position)
                JOIN pg_collation c ON c.oid=v.oid
                WHERE i.indexrelid='public.uq_news_external_source_identity'::regclass
                ORDER BY v.position
            """)
            assert [row["collname"] for row in collations] == ["C", "C"]
    asyncio.run(scenario())


def test_frontend_fixture_is_compatible(identity_dsn):
    async def scenario():
        async with isolated_database(identity_dsn) as (connection, _):
            await apply(connection)
            await connection.execute((ROOT / "docker/frontend-demo.sql").read_text(encoding="utf-8"))
            before = await rows(connection)
            await apply(connection)
            assert await rows(connection) == before
            assert await connection.fetchval("SELECT count(*) FROM companies") == 3
            assert await connection.fetchval("SELECT count(*) FROM company_news_analyses") == 3
    asyncio.run(scenario())


def test_replay_with_c_column_collation(identity_dsn):
    async def scenario():
        async with isolated_database(identity_dsn) as (connection, _):
            await connection.execute('ALTER TABLE news_articles ALTER COLUMN source_name TYPE text COLLATE "C", ALTER COLUMN source_id TYPE text COLLATE "C"')
            await apply(connection)
            await apply(connection)
            await insert(connection, source_id="Case")
            await insert(connection, source_id="case")
    asyncio.run(scenario())


def test_external_uniqueness_manual_nulls_and_case(identity_dsn):
    async def scenario():
        async with isolated_database(identity_dsn) as (connection, _):
            await apply(connection)
            await insert(connection, url="https://example.invalid/a")
            with pytest.raises(asyncpg.UniqueViolationError) as error:
                await insert(connection, url="https://example.invalid/different")
            assert error.value.sqlstate == "23505"
            assert error.value.constraint_name == "uq_news_external_source_identity"
            await insert(connection, source="another-source")
            await insert(connection, source_id="item-a")  # Preserve external ID case.
            for _ in range(2):
                await insert(connection, kind="MANUAL")
                await insert(connection, source=None)
                await insert(connection, source_id=None)
                await insert(connection, source=None, source_id=None)
            assert await connection.fetchval("SELECT count(*) FROM news_articles") == 11
            with pytest.raises(asyncpg.UniqueViolationError) as url_error:
                await insert(connection, source_id="Another-ID", url="https://example.invalid/a")
            assert url_error.value.constraint_name == "news_articles_url_key"
    asyncio.run(scenario())


@pytest.mark.parametrize("source,external_id,constraint", [
    ("UPPER", "id", "news_external_source_name_check"),
    ("bad source", "id", "news_external_source_name_check"),
    ("РёСЃС‚РѕС‡РЅРёРє", "id", "news_external_source_name_check"),
    ("", "id", "news_external_source_name_check"),
    (" wire", "id", "news_external_source_name_check"),
    ("wire", "", "news_external_source_id_check"),
    ("wire", " id", "news_external_source_id_check"),
    ("wire", "id ", "news_external_source_id_check"),
    ("wire", "\tid", "news_external_source_id_check"),
    ("wire", "id\n", "news_external_source_id_check"),
])
def test_invalid_identifiers(identity_dsn, source, external_id, constraint):
    async def scenario():
        async with isolated_database(identity_dsn) as (connection, _):
            await apply(connection)
            with pytest.raises(asyncpg.CheckViolationError) as error:
                await insert(connection, source=source, source_id=external_id)
            assert error.value.sqlstate == "23514" and error.value.constraint_name == constraint
            await insert(connection, source=source, source_id=external_id, kind="MANUAL")
    asyncio.run(scenario())


@pytest.mark.parametrize("conflict", ["duplicate", "invalid_source", "invalid_id"])
def test_bad_existing_data_rolls_back_everything(identity_dsn, conflict):
    async def scenario():
        async with isolated_database(identity_dsn) as (connection, _):
            if conflict == "duplicate":
                await insert(connection)
                await insert(connection, url="https://example.invalid/other")
            else:
                await insert(connection, source="UPPER" if conflict == "invalid_source" else "wire",
                             source_id=" padded " if conflict == "invalid_id" else "id")
            before = await rows(connection)
            with pytest.raises(asyncpg.PostgresError) as error:
                await apply(connection)
            assert error.value.sqlstate == ("23505" if conflict == "duplicate" else "23514")
            if conflict != "duplicate":
                assert error.value.constraint_name == ("news_external_source_name_check" if conflict == "invalid_source" else "news_external_source_id_check")
            assert await rows(connection) == before
            assert await connection.fetchval("SELECT to_regclass('public.uq_news_external_source_identity')") is None
            assert await connection.fetchval("SELECT count(*) FROM pg_constraint WHERE conrelid='public.news_articles'::regclass AND conname IN ('news_external_source_name_check','news_external_source_id_check')") == 0
    asyncio.run(scenario())


@pytest.mark.parametrize("definition", [
    "CREATE UNIQUE INDEX uq_news_external_source_identity ON news_articles(source_name,source_id) WHERE input_kind='EXTERNAL' AND source_name IS NOT NULL AND source_id IS NOT NULL AND btrim(source_name)<>'' AND btrim(source_id)<>''",
    "CREATE INDEX uq_news_external_source_identity ON news_articles(source_name,source_id)",
    "CREATE UNIQUE INDEX uq_news_external_source_identity ON news_articles(source_id,source_name)",
    "CREATE UNIQUE INDEX uq_news_external_source_identity ON news_articles(source_name,source_id) WHERE input_kind='MANUAL'",
])
def test_wrong_index_definition_is_not_hidden(identity_dsn, definition):
    async def scenario():
        async with isolated_database(identity_dsn) as (connection, _):
            await connection.execute(definition)
            before = await connection.fetchval("SELECT pg_get_indexdef('uq_news_external_source_identity'::regclass)")
            with pytest.raises(asyncpg.RaiseError, match="definition mismatch"):
                await apply(connection)
            assert await connection.fetchval("SELECT pg_get_indexdef('uq_news_external_source_identity'::regclass)") == before
            assert await connection.fetchval("SELECT count(*) FROM pg_constraint WHERE conrelid='public.news_articles'::regclass AND conname='news_external_source_name_check'") == 0
    asyncio.run(scenario())


@pytest.mark.parametrize("name", ["news_external_source_name_check", "news_external_source_id_check"])
def test_wrong_check_definition_is_not_hidden(identity_dsn, name):
    async def scenario():
        async with isolated_database(identity_dsn) as (connection, _):
            await connection.execute(f'ALTER TABLE news_articles ADD CONSTRAINT "{name}" CHECK (true)')
            with pytest.raises(asyncpg.RaiseError, match="definition mismatch"):
                await apply(connection)
            assert await connection.fetchval("SELECT to_regclass('uq_news_external_source_identity')") is None
    asyncio.run(scenario())


def test_concurrent_inserts_same_identity_different_urls(identity_dsn):
    async def scenario():
        async with isolated_database(identity_dsn) as (connection, name):
            await apply(connection)
            writer = await asyncpg.connect(identity_dsn, database=name)
            loser = await asyncpg.connect(identity_dsn, database=name)
            task = None
            try:
                await writer.execute("BEGIN")
                await insert(writer, url="https://example.invalid/first")
                task = asyncio.create_task(insert(loser, url="https://example.invalid/second"))
                for _ in range(100):
                    waiting = await connection.fetchval("SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=$1", loser.get_server_pid())
                    if waiting:
                        break
                    await asyncio.sleep(0.02)
                assert waiting, "Second INSERT must wait for the competing transaction"
                await writer.execute("COMMIT")
                with pytest.raises(asyncpg.UniqueViolationError) as error:
                    await asyncio.wait_for(task, timeout=5)
                assert error.value.sqlstate == "23505"
                assert error.value.constraint_name == "uq_news_external_source_identity"
                assert await connection.fetchval("SELECT count(*) FROM news_articles") == 1
            finally:
                if task is not None and not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                await writer.close()
                await loser.close()
    asyncio.run(scenario())
