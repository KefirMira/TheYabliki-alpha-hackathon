-- PostgreSQL 16. Apply after schema.sql, 002 and 003; no data rewriting.
-- Regular transactional index build: use an agreed maintenance window.
BEGIN;
SET LOCAL lock_timeout = '10s';
LOCK TABLE public.news_articles IN SHARE ROW EXCLUSIVE MODE;

DO $$
BEGIN
 IF EXISTS (
  SELECT 1 FROM public.news_articles
  WHERE input_kind='EXTERNAL'
    AND source_name IS NOT NULL AND source_id IS NOT NULL
    AND btrim(source_name)<>'' AND btrim(source_id)<>''
  GROUP BY source_name COLLATE "C", source_id COLLATE "C" HAVING count(*)>1
 ) THEN
  RAISE EXCEPTION '004: duplicate external news identities; no data changed'
   USING ERRCODE='23505';
 END IF;
END $$;

DO $$
DECLARE existing RECORD;
BEGIN
 SELECT c.oid, c.convalidated, pg_get_constraintdef(c.oid) AS definition
 INTO existing FROM pg_constraint c
 WHERE c.conrelid='public.news_articles'::regclass
   AND c.conname='news_external_source_name_check';
 IF FOUND THEN
  IF NOT existing.convalidated OR existing.definition <>
   'CHECK ((((input_kind)::text <> ''EXTERNAL''::text) OR (source_name IS NULL) OR ((source_name COLLATE "C") ~ ''^[a-z0-9._-]+$''::text)))' THEN
   RAISE EXCEPTION '004: news_external_source_name_check definition mismatch';
  END IF;
 ELSE
  ALTER TABLE public.news_articles ADD CONSTRAINT news_external_source_name_check
   CHECK (input_kind<>'EXTERNAL' OR source_name IS NULL OR source_name COLLATE "C" ~ '^[a-z0-9._-]+$');
 END IF;

 SELECT c.oid, c.convalidated, pg_get_constraintdef(c.oid) AS definition
 INTO existing FROM pg_constraint c
 WHERE c.conrelid='public.news_articles'::regclass
   AND c.conname='news_external_source_id_check';
 IF FOUND THEN
  IF NOT existing.convalidated OR existing.definition <>
   'CHECK ((((input_kind)::text <> ''EXTERNAL''::text) OR (source_id IS NULL) OR ((source_id <> ''''::text) AND ((source_id COLLATE "C") !~ ''^[[:space:]]|[[:space:]]$''::text))))' THEN
   RAISE EXCEPTION '004: news_external_source_id_check definition mismatch';
  END IF;
 ELSE
  ALTER TABLE public.news_articles ADD CONSTRAINT news_external_source_id_check
   CHECK (input_kind<>'EXTERNAL' OR source_id IS NULL OR
    (source_id<>'' AND source_id COLLATE "C" !~ '^[[:space:]]|[[:space:]]$'));
 END IF;
END $$;

DO $$
DECLARE existing RECORD;
BEGIN
 IF to_regclass('public.uq_news_external_source_identity') IS NULL THEN
  CREATE UNIQUE INDEX uq_news_external_source_identity
   ON public.news_articles (source_name COLLATE "C", source_id COLLATE "C")
   WHERE input_kind='EXTERNAL'
     AND source_name IS NOT NULL AND source_id IS NOT NULL
     AND btrim(source_name)<>'' AND btrim(source_id)<>'';
 ELSE
  SELECT i.indisvalid, i.indisready, i.indislive,
         (i.indcollation[0]='pg_catalog."C"'::regcollation AND
          i.indcollation[1]='pg_catalog."C"'::regcollation) AS c_collation,
         pg_get_indexdef(i.indexrelid) AS definition
  INTO existing FROM pg_index i
  WHERE i.indexrelid='public.uq_news_external_source_identity'::regclass;
  IF NOT FOUND THEN
   RAISE EXCEPTION '004: uq_news_external_source_identity is not an index';
  END IF;
  -- Deparser may omit COLLATE when it equals the column default. Check OIDs too.
  IF NOT existing.indisvalid OR NOT existing.indisready OR NOT existing.indislive OR
   NOT existing.c_collation OR replace(existing.definition, ' COLLATE "C"', '') <>
   'CREATE UNIQUE INDEX uq_news_external_source_identity ON public.news_articles USING btree (source_name, source_id) WHERE (((input_kind)::text = ''EXTERNAL''::text) AND (source_name IS NOT NULL) AND (source_id IS NOT NULL) AND (btrim(source_name) <> ''''::text) AND (btrim(source_id) <> ''''::text))' THEN
   RAISE EXCEPTION '004: uq_news_external_source_identity definition mismatch';
  END IF;
 END IF;
END $$;
COMMIT;
