-- Additive authentication/ACL. No implicit grants for historical data.
BEGIN;
CREATE TABLE IF NOT EXISTS public.auth_users (
 id UUID PRIMARY KEY,
 login TEXT COLLATE "C" NOT NULL UNIQUE,
 password_hash TEXT NOT NULL CHECK (password_hash LIKE '$argon2id$%'),
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 CHECK (login ~ '^[a-z0-9][a-z0-9._-]{2,63}$')
);
CREATE TABLE IF NOT EXISTS public.auth_sessions (
 token_hash VARCHAR(64) COLLATE "C" PRIMARY KEY CHECK (token_hash ~ '^[0-9a-f]{64}$'),
 user_id UUID NOT NULL REFERENCES public.auth_users(id) ON DELETE RESTRICT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 expires_at TIMESTAMPTZ NOT NULL,
 revoked_at TIMESTAMPTZ,
 CHECK (expires_at > created_at),
 CHECK (revoked_at IS NULL OR revoked_at >= created_at)
);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON public.auth_sessions(user_id);
CREATE TABLE IF NOT EXISTS public.auth_user_companies (
 user_id UUID NOT NULL REFERENCES public.auth_users(id) ON DELETE RESTRICT,
 company_id BIGINT NOT NULL REFERENCES public.companies(id) ON DELETE RESTRICT,
 can_analyze BOOLEAN NOT NULL DEFAULT FALSE,
 PRIMARY KEY (user_id, company_id)
);
CREATE INDEX IF NOT EXISTS idx_auth_memberships_company ON public.auth_user_companies(company_id);
CREATE TABLE IF NOT EXISTS public.auth_news_grants (
 user_id UUID NOT NULL REFERENCES public.auth_users(id) ON DELETE RESTRICT,
 news_id BIGINT NOT NULL REFERENCES public.news_articles(id) ON DELETE RESTRICT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY (user_id, news_id)
);
CREATE INDEX IF NOT EXISTS idx_auth_news_grants_news ON public.auth_news_grants(news_id);
COMMIT;
