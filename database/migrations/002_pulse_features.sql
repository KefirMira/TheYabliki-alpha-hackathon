-- Пульс бизнеса: аддитивное расширение исходной схемы.
-- Применять ПОСЛЕ schema.sql; не изменяет seed и существующие записи.
BEGIN;

-- Структурированный результат AI. Точные баллы допустимы только при наличии методики.
ALTER TABLE company_news_analyses ADD COLUMN IF NOT EXISTS insight_kind VARCHAR(20);
ALTER TABLE company_news_analyses ADD COLUMN IF NOT EXISTS relevance_level VARCHAR(10);
ALTER TABLE company_news_analyses ADD COLUMN IF NOT EXISTS impact_level VARCHAR(10);
ALTER TABLE company_news_analyses ADD COLUMN IF NOT EXISTS evidence_strength VARCHAR(10);
ALTER TABLE company_news_analyses ADD COLUMN IF NOT EXISTS headline TEXT;
ALTER TABLE company_news_analyses ADD COLUMN IF NOT EXISTS facts JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE company_news_analyses ADD COLUMN IF NOT EXISTS risks JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE company_news_analyses ADD COLUMN IF NOT EXISTS opportunities JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE company_news_analyses ADD COLUMN IF NOT EXISTS recommendations JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE company_news_analyses ADD COLUMN IF NOT EXISTS scenarios JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE company_news_analyses ADD COLUMN IF NOT EXISTS validation JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE company_news_analyses ADD COLUMN IF NOT EXISTS source_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE company_news_analyses ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE TABLE IF NOT EXISTS information_sources (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 name TEXT NOT NULL,
 source_type VARCHAR(30) NOT NULL,
 url TEXT,
 last_checked_at TIMESTAMPTZ,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 CONSTRAINT information_sources_type_check CHECK (source_type IN ('BANK_ANALYTICS','STATISTICS','REGULATOR','EXCHANGE','MEDIA','USER_DOCUMENT','OTHER'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_information_sources_url ON information_sources(url) WHERE url IS NOT NULL;

CREATE TABLE IF NOT EXISTS company_contexts (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 company_id BIGINT NOT NULL UNIQUE REFERENCES companies(id) ON DELETE RESTRICT,
 business_description TEXT,
 additional_notes TEXT,
 structured_context JSONB NOT NULL DEFAULT '{}'::jsonb,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS company_documents (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
 original_filename TEXT NOT NULL,
 mime_type TEXT,
 size_bytes BIGINT,
 storage_key TEXT NOT NULL,
 sha256 CHAR(64),
 processing_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
 processing_error TEXT,
 extracted_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
 uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 processed_at TIMESTAMPTZ,
 CONSTRAINT company_documents_status_check CHECK (processing_status IN ('PENDING','PROCESSING','COMPLETED','FAILED')),
 CONSTRAINT company_documents_size_check CHECK (size_bytes IS NULL OR size_bytes >= 0)
);
CREATE INDEX IF NOT EXISTS idx_company_documents_company ON company_documents(company_id);

-- Избранное/скрытие/просмотр зависят от пользователя, а не от самого инсайта.
-- В MVP user_key = идентификатор пользователя из auth-слоя; не хранить здесь пароли.
CREATE TABLE IF NOT EXISTS company_insight_states (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 company_news_analysis_id BIGINT NOT NULL REFERENCES company_news_analyses(id) ON DELETE RESTRICT,
 user_key TEXT NOT NULL,
 is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
 is_hidden BOOLEAN NOT NULL DEFAULT FALSE,
 viewed_at TIMESTAMPTZ,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 UNIQUE (company_news_analysis_id, user_key)
);
CREATE INDEX IF NOT EXISTS idx_insight_states_user ON company_insight_states(user_key);

CREATE TABLE IF NOT EXISTS insight_updates (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 company_news_analysis_id BIGINT NOT NULL REFERENCES company_news_analyses(id) ON DELETE RESTRICT,
 triggering_news_id BIGINT REFERENCES news_articles(id) ON DELETE RESTRICT,
 verification_status VARCHAR(20) NOT NULL,
 update_summary TEXT NOT NULL,
 supporting_data JSONB NOT NULL DEFAULT '[]'::jsonb,
 checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 CONSTRAINT insight_updates_status_check CHECK (verification_status IN ('UNVERIFIED','CONFIRMED','REFUTED','UPDATED','EXPIRED'))
);
CREATE INDEX IF NOT EXISTS idx_insight_updates_insight_time ON insight_updates(company_news_analysis_id, checked_at DESC);

-- Связь доказательства с каталогом источников, в т.ч. PDF.
ALTER TABLE insight_evidence ADD COLUMN IF NOT EXISTS information_source_id BIGINT REFERENCES information_sources(id) ON DELETE RESTRICT;
ALTER TABLE insight_evidence ADD COLUMN IF NOT EXISTS document_name TEXT;
ALTER TABLE insight_evidence ADD COLUMN IF NOT EXISTS document_page INTEGER;
ALTER TABLE insight_evidence ADD COLUMN IF NOT EXISTS chunk_id INTEGER;
ALTER TABLE insight_evidence ADD COLUMN IF NOT EXISTS document_date DATE;
CREATE INDEX IF NOT EXISTS idx_evidence_source ON insight_evidence(information_source_id);

-- Техническая целостность и частые запросы по платежам.
CREATE INDEX IF NOT EXISTS idx_payments_payer_source ON company_payments(payer_source_company_id);

-- Ручной анализ новостей: текст может не иметь внешнего URL.
ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS input_kind VARCHAR(20) NOT NULL DEFAULT 'EXTERNAL';
ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS submitted_by_user_key TEXT;
ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS information_source_id BIGINT REFERENCES information_sources(id) ON DELETE RESTRICT;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'news_articles_input_kind_check' AND conrelid = 'news_articles'::regclass) THEN
  ALTER TABLE news_articles ADD CONSTRAINT news_articles_input_kind_check CHECK (input_kind IN ('EXTERNAL','MANUAL'));
 END IF;
END $$;

COMMIT;
