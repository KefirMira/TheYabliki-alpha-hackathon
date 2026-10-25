-- Dedicated new submission database only; never a shared/demo volume.
SELECT format('COMMENT ON DATABASE %I IS %L', current_database(), 'pulse:isolated-company-import:v1') \gexec
