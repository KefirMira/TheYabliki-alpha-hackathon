BEGIN;
CREATE TABLE IF NOT EXISTS companies (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 source_id TEXT UNIQUE, name TEXT NOT NULL, inn VARCHAR(12), ogrn VARCHAR(15),
 industry TEXT, region TEXT, website TEXT, revenue NUMERIC(18,2), revenue_year SMALLINT,
 employee_count INTEGER, client_status VARCHAR(30), source_data JSONB NOT NULL DEFAULT '{}'::jsonb,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 CHECK (revenue IS NULL OR revenue >= 0),
 CHECK (revenue_year IS NULL OR revenue_year BETWEEN 1800 AND 2200),
 CHECK (employee_count IS NULL OR employee_count >= 0),
 CHECK (client_status IS NULL OR client_status IN ('CLIENT','PROSPECT','CLOSED_CLIENT'))
);
CREATE TABLE IF NOT EXISTS persons (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, source_id TEXT UNIQUE,
 full_name TEXT NOT NULL, first_name TEXT, last_name TEXT, middle_name TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS company_person_links (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, source_id TEXT UNIQUE,
 company_id BIGINT REFERENCES companies(id) ON DELETE RESTRICT,
 person_id BIGINT REFERENCES persons(id) ON DELETE RESTRICT,
 source_company_id TEXT, source_person_id TEXT, role TEXT, relation_type TEXT,
 start_date DATE, end_date DATE, source_name TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 CHECK (start_date IS NULL OR end_date IS NULL OR end_date >= start_date),
 CHECK (company_id IS NOT NULL OR source_company_id IS NOT NULL),
 CHECK (person_id IS NOT NULL OR source_person_id IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS company_payments (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, source_id TEXT UNIQUE,
 company_id BIGINT REFERENCES companies(id) ON DELETE RESTRICT, source_company_id TEXT, payer_source_company_id TEXT,
 amount NUMERIC(18,2), payment_count BIGINT, currency VARCHAR(3), payment_date DATE, period_start DATE, period_end DATE,
 payment_type TEXT, description TEXT, source_name TEXT, source_data JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 CHECK (amount IS NULL OR amount >= 0),
 CHECK (period_start IS NULL OR period_end IS NULL OR period_end >= period_start),
 CHECK (company_id IS NOT NULL OR source_company_id IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS news_articles (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, source_id TEXT, source_name TEXT, url TEXT UNIQUE,
 title TEXT NOT NULL, content TEXT, published_at TIMESTAMPTZ, collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 language VARCHAR(10), content_hash VARCHAR(64), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS analysis_runs (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 company_id BIGINT REFERENCES companies(id) ON DELETE RESTRICT,
 analysis_type VARCHAR(50) NOT NULL, status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
 model_name TEXT, prompt_version TEXT, started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ,
 result_summary TEXT, error_message TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 CHECK (status IN ('PENDING','RUNNING','COMPLETED','FAILED')),
 CHECK (finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at)
);
CREATE TABLE IF NOT EXISTS company_news_analyses (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 analysis_run_id BIGINT NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
 company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
 news_id BIGINT NOT NULL REFERENCES news_articles(id) ON DELETE RESTRICT,
 relevance_score NUMERIC(5,4), sentiment VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN',
 impact_type VARCHAR(50), impact_summary TEXT, confidence_score NUMERIC(5,4),
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 CHECK (relevance_score IS NULL OR relevance_score BETWEEN 0 AND 1),
 CHECK (confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1),
 CHECK (sentiment IN ('POSITIVE','NEUTRAL','NEGATIVE','MIXED','UNKNOWN'))
);
CREATE TABLE IF NOT EXISTS insight_evidence (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 company_news_analysis_id BIGINT NOT NULL REFERENCES company_news_analyses(id) ON DELETE RESTRICT,
 news_id BIGINT REFERENCES news_articles(id) ON DELETE RESTRICT,
 evidence_type VARCHAR(30) NOT NULL, evidence_text TEXT NOT NULL, source_url TEXT,
 start_offset INTEGER, end_offset INTEGER, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 CHECK ((start_offset IS NULL OR start_offset >= 0) AND (end_offset IS NULL OR end_offset >= 0)
   AND (start_offset IS NULL OR end_offset IS NULL OR end_offset >= start_offset))
);
-- Миграции для уже созданной базы: добавляем поля исходных CSV без потери данных.
ALTER TABLE companies ADD COLUMN IF NOT EXISTS source_data JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE company_person_links ADD COLUMN IF NOT EXISTS city_name TEXT;
ALTER TABLE company_person_links ADD COLUMN IF NOT EXISTS rc_name TEXT;
ALTER TABLE company_person_links ADD COLUMN IF NOT EXISTS source_data JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE company_payments ADD COLUMN IF NOT EXISTS payer_source_company_id TEXT;
ALTER TABLE company_payments ADD COLUMN IF NOT EXISTS payment_count BIGINT;
ALTER TABLE company_payments ADD COLUMN IF NOT EXISTS source_data JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);
CREATE INDEX IF NOT EXISTS idx_companies_inn ON companies(inn);
CREATE INDEX IF NOT EXISTS idx_companies_client_status ON companies(client_status);
CREATE INDEX IF NOT EXISTS idx_persons_full_name ON persons(full_name);
CREATE INDEX IF NOT EXISTS idx_links_company ON company_person_links(company_id);
CREATE INDEX IF NOT EXISTS idx_links_person ON company_person_links(person_id);
CREATE INDEX IF NOT EXISTS idx_links_source_company ON company_person_links(source_company_id);
CREATE INDEX IF NOT EXISTS idx_links_source_person ON company_person_links(source_person_id);
CREATE INDEX IF NOT EXISTS idx_payments_company ON company_payments(company_id);
CREATE INDEX IF NOT EXISTS idx_payments_source_company ON company_payments(source_company_id);
CREATE INDEX IF NOT EXISTS idx_payments_date ON company_payments(payment_date);
CREATE INDEX IF NOT EXISTS idx_news_published_at ON news_articles(published_at);
CREATE INDEX IF NOT EXISTS idx_news_content_hash ON news_articles(content_hash);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_company ON analysis_runs(company_id);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_status ON analysis_runs(status);
CREATE INDEX IF NOT EXISTS idx_news_analyses_company ON company_news_analyses(company_id);
CREATE INDEX IF NOT EXISTS idx_news_analyses_news ON company_news_analyses(news_id);
CREATE INDEX IF NOT EXISTS idx_news_analyses_run ON company_news_analyses(analysis_run_id);
CREATE INDEX IF NOT EXISTS idx_evidence_analysis ON insight_evidence(company_news_analysis_id);
COMMIT;
