SELECT 'companies',count(*),md5(string_agg(to_jsonb(t)::text,E'\n' ORDER BY id)) FROM companies t
UNION ALL SELECT 'persons',count(*),md5(string_agg(to_jsonb(t)::text,E'\n' ORDER BY id)) FROM persons t
UNION ALL SELECT 'links',count(*),md5(string_agg(to_jsonb(t)::text,E'\n' ORDER BY id)) FROM company_person_links t
UNION ALL SELECT 'payments',count(*),md5(string_agg(to_jsonb(t)::text,E'\n' ORDER BY id)) FROM company_payments t;
