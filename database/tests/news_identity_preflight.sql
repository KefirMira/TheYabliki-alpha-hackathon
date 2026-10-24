-- Read-only preflight for an EXISTING demo database. No migration or data writes.
BEGIN TRANSACTION READ ONLY;
SELECT current_database() AS database_name, current_setting('server_version') AS postgres_version;
SELECT 'duplicate_external_pair_groups' AS check_name, count(*) AS failures FROM (
 SELECT 1 FROM public.news_articles
 WHERE input_kind='EXTERNAL' AND source_name IS NOT NULL AND source_id IS NOT NULL
   AND btrim(source_name)<>'' AND btrim(source_id)<>''
 GROUP BY source_name COLLATE "C", source_id COLLATE "C" HAVING count(*)>1
) duplicates
UNION ALL
SELECT 'invalid_external_identifiers', count(*) FROM public.news_articles
WHERE input_kind='EXTERNAL' AND (
 (source_name IS NOT NULL AND NOT (source_name COLLATE "C" ~ '^[a-z0-9._-]+$')) OR
 (source_id IS NOT NULL AND (source_id='' OR source_id COLLATE "C" ~ '^[[:space:]]|[[:space:]]$'))
);
SELECT indexname, indexdef FROM pg_indexes
WHERE schemaname='public' AND tablename='news_articles' ORDER BY indexname;
COMMIT;
