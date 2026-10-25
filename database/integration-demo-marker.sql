-- Mounted only in the dedicated, new integration-demo PostgreSQL volume.
-- Never run against shared databases. The seed does not create this marker.
COMMENT ON DATABASE test_integration_demo IS 'pulse:isolated-integration-demo:v1';
