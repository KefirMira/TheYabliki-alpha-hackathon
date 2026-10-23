-- Additive PostgreSQL 16 migration. Never registers or rewrites legacy history.
BEGIN;
SET LOCAL lock_timeout = '10s';
DO $signature$ DECLARE actual TEXT; BEGIN
 IF to_regclass('public.news_analysis_jobs') IS NOT NULL OR to_regclass('public.news_analysis_attempts') IS NOT NULL THEN
 SELECT value INTO actual FROM (
SELECT md5(string_agg(item, E'\n' ORDER BY item)) FROM (
 SELECT 'column:' || c.relname || ':' || a.attnum || ':' || a.attname || ':' ||
   format_type(a.atttypid,a.atttypmod) || ':' || a.attnotnull || ':' ||
   a.attidentity::text || ':' || coalesce(pg_get_expr(d.adbin,d.adrelid),'') AS item
 FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
 LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
 WHERE a.attrelid IN (to_regclass('public.news_analysis_jobs'),to_regclass('public.news_analysis_attempts'))
   AND a.attnum>0 AND NOT a.attisdropped
 UNION ALL
 SELECT 'constraint:' || c.conrelid::regclass::text || ':' || c.conname || ':' ||
   c.contype::text || ':' || c.convalidated || ':' || pg_get_constraintdef(c.oid)
 FROM pg_constraint c WHERE c.conrelid IN
   (to_regclass('public.news_analysis_jobs'),to_regclass('public.news_analysis_attempts'))
   OR (c.conrelid=to_regclass('public.analysis_runs') AND c.conname='uq_analysis_runs_id_company')
   OR (c.conrelid=to_regclass('public.company_news_analyses') AND c.conname='uq_news_analysis_identity')
 UNION ALL
 SELECT 'index:' || pg_get_indexdef(i.indexrelid) || ':' || i.indisvalid || ':' || i.indisready || ':' || i.indislive
 FROM pg_index i WHERE i.indrelid IN
   (to_regclass('public.news_analysis_jobs'),to_regclass('public.news_analysis_attempts'))
   OR i.indexrelid IN (to_regclass('public.uq_analysis_runs_id_company'),to_regclass('public.uq_news_analysis_identity'))
) signature
) s(value);
 IF actual IS DISTINCT FROM 'f2d8b5e9d6d287f94a5dd4f10976f32a' THEN
  RAISE EXCEPTION '005: catalogue definition mismatch; no automatic repair';
 END IF;
 END IF;
END $signature$;


DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_constraint WHERE conrelid='public.analysis_runs'::regclass AND conname='uq_analysis_runs_id_company') THEN
  ALTER TABLE public.analysis_runs ADD CONSTRAINT uq_analysis_runs_id_company UNIQUE (id, company_id);
 END IF;
 IF NOT EXISTS (SELECT FROM pg_constraint WHERE conrelid='public.company_news_analyses'::regclass AND conname='uq_news_analysis_identity') THEN
  ALTER TABLE public.company_news_analyses ADD CONSTRAINT uq_news_analysis_identity UNIQUE (id, analysis_run_id, company_id, news_id);
 END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.news_analysis_jobs (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 company_id BIGINT NOT NULL REFERENCES public.companies(id) ON DELETE RESTRICT,
 news_id BIGINT NOT NULL REFERENCES public.news_articles(id) ON DELETE RESTRICT,
 max_attempts SMALLINT NOT NULL DEFAULT 2 CHECK (max_attempts BETWEEN 1 AND 2),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE (company_id, news_id),
 UNIQUE (id, company_id, news_id)
);

CREATE TABLE IF NOT EXISTS public.news_analysis_attempts (
 job_id BIGINT NOT NULL,
 attempt_no SMALLINT NOT NULL CHECK (attempt_no BETWEEN 1 AND 2),
 company_id BIGINT NOT NULL,
 news_id BIGINT NOT NULL,
 run_id BIGINT NOT NULL UNIQUE,
 claim_token UUID NOT NULL UNIQUE,
 reserved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 deadline_at TIMESTAMPTZ NOT NULL,
 dispatch_started_at TIMESTAMPTZ,
 retry_policy VARCHAR(20) NOT NULL DEFAULT 'BLOCKED',
 retry_not_before TIMESTAMPTZ,
 retry_reason TEXT,
 retry_authorized_by TEXT,
 retry_authorized_at TIMESTAMPTZ,
 insight_id BIGINT,
 response_payload JSONB,
 PRIMARY KEY (job_id, attempt_no),
 FOREIGN KEY (job_id, company_id, news_id) REFERENCES public.news_analysis_jobs(id, company_id, news_id) ON DELETE RESTRICT,
 FOREIGN KEY (run_id, company_id) REFERENCES public.analysis_runs(id, company_id) ON DELETE RESTRICT,
 FOREIGN KEY (insight_id, run_id, company_id, news_id) REFERENCES public.company_news_analyses(id, analysis_run_id, company_id, news_id) ON DELETE RESTRICT,
 CHECK (deadline_at > reserved_at),
 CHECK (dispatch_started_at IS NULL OR dispatch_started_at >= reserved_at),
 CHECK (retry_policy IN ('BLOCKED','SAFE','MANUAL_APPROVED','REVIEW_REQUIRED')),
 CHECK (retry_policy <> 'MANUAL_APPROVED' OR
   (retry_authorized_by IS NOT NULL AND retry_authorized_at IS NOT NULL AND retry_reason IS NOT NULL)),
 CHECK ((insight_id IS NULL AND response_payload IS NULL) OR
   (insight_id IS NOT NULL AND response_payload IS NOT NULL AND jsonb_typeof(response_payload)='object'))
);

CREATE INDEX IF NOT EXISTS idx_news_analysis_jobs_news ON public.news_analysis_jobs(news_id);
CREATE INDEX IF NOT EXISTS idx_news_analysis_attempts_deadline
 ON public.news_analysis_attempts(deadline_at) WHERE insight_id IS NULL;

-- Strict catalogue signature is checked below, including replay (not just names).
DO $signature$ DECLARE actual TEXT; BEGIN
 SELECT value INTO actual FROM (
SELECT md5(string_agg(item, E'\n' ORDER BY item)) FROM (
 SELECT 'column:' || c.relname || ':' || a.attnum || ':' || a.attname || ':' ||
   format_type(a.atttypid,a.atttypmod) || ':' || a.attnotnull || ':' ||
   a.attidentity::text || ':' || coalesce(pg_get_expr(d.adbin,d.adrelid),'') AS item
 FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
 LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
 WHERE a.attrelid IN (to_regclass('public.news_analysis_jobs'),to_regclass('public.news_analysis_attempts'))
   AND a.attnum>0 AND NOT a.attisdropped
 UNION ALL
 SELECT 'constraint:' || c.conrelid::regclass::text || ':' || c.conname || ':' ||
   c.contype::text || ':' || c.convalidated || ':' || pg_get_constraintdef(c.oid)
 FROM pg_constraint c WHERE c.conrelid IN
   (to_regclass('public.news_analysis_jobs'),to_regclass('public.news_analysis_attempts'))
   OR (c.conrelid=to_regclass('public.analysis_runs') AND c.conname='uq_analysis_runs_id_company')
   OR (c.conrelid=to_regclass('public.company_news_analyses') AND c.conname='uq_news_analysis_identity')
 UNION ALL
 SELECT 'index:' || pg_get_indexdef(i.indexrelid) || ':' || i.indisvalid || ':' || i.indisready || ':' || i.indislive
 FROM pg_index i WHERE i.indrelid IN
   (to_regclass('public.news_analysis_jobs'),to_regclass('public.news_analysis_attempts'))
   OR i.indexrelid IN (to_regclass('public.uq_analysis_runs_id_company'),to_regclass('public.uq_news_analysis_identity'))
) signature
) s(value);
 IF actual IS DISTINCT FROM 'f2d8b5e9d6d287f94a5dd4f10976f32a' THEN
  RAISE EXCEPTION '005: catalogue definition mismatch; no automatic repair';
 END IF;
END $signature$;

COMMIT;
