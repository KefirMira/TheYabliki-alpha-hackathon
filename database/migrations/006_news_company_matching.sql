-- Deterministic mentions only; no analysis_runs, AI evidence or original news writes.
BEGIN;
SET LOCAL lock_timeout = '10s';
DO $check$ DECLARE actual TEXT; BEGIN
 IF to_regclass('public.company_verified_names') IS NOT NULL OR to_regclass('public.news_company_match_runs') IS NOT NULL OR to_regclass('public.news_company_match_candidates') IS NOT NULL THEN
SELECT value INTO actual FROM (
SELECT md5(string_agg(item, E'\n' ORDER BY item)) FROM (
 SELECT 'column:' || c.relname || ':' || a.attnum || ':' || a.attname || ':' ||
   format_type(a.atttypid,a.atttypmod) || ':' || a.attnotnull || ':' ||
   a.attidentity::text || ':' || coalesce(pg_get_expr(d.adbin,d.adrelid),'') AS item
 FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
 LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
 WHERE c.relnamespace='public'::regnamespace
   AND c.relname IN ('company_verified_names','news_company_match_runs','news_company_match_candidates')
   AND a.attnum>0 AND NOT a.attisdropped
 UNION ALL
 SELECT 'constraint:' || c.conrelid::regclass::text || ':' || c.conname || ':' ||
   c.contype::text || ':' || c.convalidated || ':' || pg_get_constraintdef(c.oid)
 FROM pg_constraint c WHERE c.conrelid IN (to_regclass('public.company_verified_names'),
   to_regclass('public.news_company_match_runs'),to_regclass('public.news_company_match_candidates'))
 UNION ALL
 SELECT 'index:' || pg_get_indexdef(i.indexrelid) || ':' || i.indisvalid || ':' || i.indisready || ':' || i.indislive
 FROM pg_index i WHERE i.indrelid IN (to_regclass('public.company_verified_names'),
   to_regclass('public.news_company_match_runs'),to_regclass('public.news_company_match_candidates'))
) signature
) s(value);
 IF actual IS DISTINCT FROM 'd354f6d0081e3e55ebb9d920ded822d7' THEN
 RAISE EXCEPTION '006: catalogue definition mismatch; no automatic repair';
 END IF;
 END IF;
END $check$;
CREATE TABLE IF NOT EXISTS public.company_verified_names (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 company_id BIGINT NOT NULL REFERENCES public.companies(id) ON DELETE RESTRICT,
 name TEXT NOT NULL CHECK (btrim(name) <> ''),
 verified_by TEXT NOT NULL CHECK (btrim(verified_by) <> ''),
 provenance TEXT NOT NULL CHECK (btrim(provenance) <> ''),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE (company_id, name)
);
CREATE TABLE IF NOT EXISTS public.news_company_match_runs (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 news_id BIGINT NOT NULL REFERENCES public.news_articles(id) ON DELETE RESTRICT,
 algorithm_version TEXT NOT NULL CHECK (btrim(algorithm_version) <> ''),
 news_hash TEXT NOT NULL CHECK (news_hash ~ '^[a-f0-9]{64}$'),
 dictionary_hash TEXT NOT NULL CHECK (dictionary_hash ~ '^[a-f0-9]{64}$'),
 status TEXT NOT NULL CHECK (status IN ('MATCHED','AMBIGUOUS','NO_MATCH')),
 news_snapshot JSONB NOT NULL CHECK (jsonb_typeof(news_snapshot) = 'object'),
 created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 UNIQUE (news_id, algorithm_version, news_hash, dictionary_hash)
);
CREATE INDEX IF NOT EXISTS ix_news_company_match_latest ON public.news_company_match_runs(news_id, id DESC);
CREATE TABLE IF NOT EXISTS public.news_company_match_candidates (
 run_id BIGINT NOT NULL REFERENCES public.news_company_match_runs(id) ON DELETE RESTRICT,
 company_id BIGINT NOT NULL REFERENCES public.companies(id) ON DELETE RESTRICT,
 company_snapshot JSONB NOT NULL CHECK (jsonb_typeof(company_snapshot) = 'object'),
 evidence JSONB NOT NULL CHECK (jsonb_typeof(evidence) = 'array' AND jsonb_array_length(evidence) > 0),
 PRIMARY KEY (run_id, company_id)
);
CREATE INDEX IF NOT EXISTS ix_news_company_match_company ON public.news_company_match_candidates(company_id, run_id);
DO $check$ DECLARE actual TEXT; BEGIN
SELECT value INTO actual FROM (
SELECT md5(string_agg(item, E'\n' ORDER BY item)) FROM (
 SELECT 'column:' || c.relname || ':' || a.attnum || ':' || a.attname || ':' ||
   format_type(a.atttypid,a.atttypmod) || ':' || a.attnotnull || ':' ||
   a.attidentity::text || ':' || coalesce(pg_get_expr(d.adbin,d.adrelid),'') AS item
 FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
 LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
 WHERE c.relnamespace='public'::regnamespace
   AND c.relname IN ('company_verified_names','news_company_match_runs','news_company_match_candidates')
   AND a.attnum>0 AND NOT a.attisdropped
 UNION ALL
 SELECT 'constraint:' || c.conrelid::regclass::text || ':' || c.conname || ':' ||
   c.contype::text || ':' || c.convalidated || ':' || pg_get_constraintdef(c.oid)
 FROM pg_constraint c WHERE c.conrelid IN (to_regclass('public.company_verified_names'),
   to_regclass('public.news_company_match_runs'),to_regclass('public.news_company_match_candidates'))
 UNION ALL
 SELECT 'index:' || pg_get_indexdef(i.indexrelid) || ':' || i.indisvalid || ':' || i.indisready || ':' || i.indislive
 FROM pg_index i WHERE i.indrelid IN (to_regclass('public.company_verified_names'),
   to_regclass('public.news_company_match_runs'),to_regclass('public.news_company_match_candidates'))
) signature
) s(value);
 IF actual IS DISTINCT FROM 'd354f6d0081e3e55ebb9d920ded822d7' THEN
 RAISE EXCEPTION '006: catalogue definition mismatch; no automatic repair';
 END IF;
END $check$;
COMMIT;
