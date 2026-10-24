"""Read-only PostgreSQL 16 catalogue signature for the additive 005 objects."""
JOB_SCHEMA_SQL = r"""
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
"""
JOB_SCHEMA_SIGNATURE = "f2d8b5e9d6d287f94a5dd4f10976f32a"
