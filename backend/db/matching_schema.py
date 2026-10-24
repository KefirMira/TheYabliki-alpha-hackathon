"""Read-only catalogue signature of migration 006; shared with its replay check."""
MATCH_SCHEMA_SQL = r"""
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
"""
MATCH_SCHEMA_SIGNATURE = 'd354f6d0081e3e55ebb9d920ded822d7'
