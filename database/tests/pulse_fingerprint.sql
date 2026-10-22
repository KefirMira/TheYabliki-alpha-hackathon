SELECT 'sources',count(*),md5(string_agg(to_jsonb(t)::text,E'\n' ORDER BY id)) FROM information_sources t
UNION ALL SELECT 'contexts',count(*),md5(string_agg(to_jsonb(t)::text,E'\n' ORDER BY id)) FROM company_contexts t
UNION ALL SELECT 'documents',count(*),md5(string_agg(to_jsonb(t)::text,E'\n' ORDER BY id)) FROM company_documents t
UNION ALL SELECT 'news',count(*),md5(string_agg(to_jsonb(t)::text,E'\n' ORDER BY id)) FROM news_articles t
UNION ALL SELECT 'runs',count(*),md5(string_agg(to_jsonb(t)::text,E'\n' ORDER BY id)) FROM analysis_runs t
UNION ALL SELECT 'analyses',count(*),md5(string_agg(to_jsonb(t)::text,E'\n' ORDER BY id)) FROM company_news_analyses t
UNION ALL SELECT 'evidence',count(*),md5(string_agg(to_jsonb(t)::text,E'\n' ORDER BY id)) FROM insight_evidence t
UNION ALL SELECT 'states',count(*),md5(string_agg(to_jsonb(t)::text,E'\n' ORDER BY id)) FROM company_insight_states t
UNION ALL SELECT 'updates',count(*),md5(string_agg(to_jsonb(t)::text,E'\n' ORDER BY id)) FROM insight_updates t;
