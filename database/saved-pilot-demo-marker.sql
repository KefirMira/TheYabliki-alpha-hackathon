-- Only mounted when initializing a NEW dedicated saved-pilot demo volume.
SELECT format('COMMENT ON DATABASE %I IS %L', current_database(), 'pulse:isolated-saved-pilot-demo:v1') \gexec
