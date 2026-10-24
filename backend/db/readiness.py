"""Read-only PostgreSQL 16 catalogue verification aligned with migration 004."""
from sqlalchemy import text

SOURCE_NAME_CHECK = """CHECK ((((input_kind)::text <> 'EXTERNAL'::text) OR (source_name IS NULL) OR ((source_name COLLATE "C") ~ '^[a-z0-9._-]+$'::text)))"""
SOURCE_ID_CHECK = """CHECK ((((input_kind)::text <> 'EXTERNAL'::text) OR (source_id IS NULL) OR ((source_id <> ''::text) AND ((source_id COLLATE "C") !~ '^[[:space:]]|[[:space:]]$'::text))))"""
IDENTITY_INDEX = """CREATE UNIQUE INDEX uq_news_external_source_identity ON public.news_articles USING btree (source_name, source_id) WHERE (((input_kind)::text = 'EXTERNAL'::text) AND (source_name IS NOT NULL) AND (source_id IS NOT NULL) AND (btrim(source_name) <> ''::text) AND (btrim(source_id) <> ''::text))"""

IDENTITY_OBJECTS_QUERY = text('''
SELECT
 (SELECT count(*) = 2 FROM pg_catalog.pg_constraint c
  WHERE c.conrelid = to_regclass('public.news_articles')
    AND c.contype = 'c' AND c.convalidated
    AND ((c.conname = 'news_external_source_name_check'
          AND pg_get_constraintdef(c.oid) = :name_check)
      OR (c.conname = 'news_external_source_id_check'
          AND pg_get_constraintdef(c.oid) = :id_check)))
 AND EXISTS (
  SELECT 1 FROM pg_catalog.pg_index i
  WHERE i.indexrelid = to_regclass('public.uq_news_external_source_identity')
    AND i.indrelid = to_regclass('public.news_articles')
    AND i.indisunique AND i.indisvalid AND i.indisready AND i.indislive
    AND i.indcollation[0] = 'pg_catalog."C"'::regcollation
    AND i.indcollation[1] = 'pg_catalog."C"'::regcollation
    AND replace(pg_get_indexdef(i.indexrelid), ' COLLATE "C"', '') = :index_definition
 )
''')


async def news_identity_ready(session) -> bool:
    result = await session.execute(IDENTITY_OBJECTS_QUERY, {
        "name_check": SOURCE_NAME_CHECK, "id_check": SOURCE_ID_CHECK,
        "index_definition": IDENTITY_INDEX,
    })
    return result.scalar_one() is True
