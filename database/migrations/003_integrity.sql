-- Apply after schema.sql and 002. No new application tables.
BEGIN;
SET LOCAL lock_timeout = '10s';

DO $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='company_news_analyses'::regclass AND conname='pulse_levels_check') THEN
  ALTER TABLE company_news_analyses ADD CONSTRAINT pulse_levels_check CHECK (
   (insight_kind IS NULL OR insight_kind IN ('risk','opportunity','mixed','information')) AND
   (relevance_level IS NULL OR relevance_level IN ('high','medium','low','unknown')) AND
   (impact_level IS NULL OR impact_level IN ('high','medium','low','unknown')) AND
   (evidence_strength IS NULL OR evidence_strength IN ('high','medium','low','unknown'))
  );
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='company_news_analyses'::regclass AND conname='pulse_analysis_json_check') THEN
  ALTER TABLE company_news_analyses ADD CONSTRAINT pulse_analysis_json_check CHECK (
   jsonb_typeof(facts)='array' AND jsonb_typeof(risks)='array' AND
   jsonb_typeof(opportunities)='array' AND jsonb_typeof(recommendations)='array' AND
   jsonb_typeof(scenarios)='array' AND jsonb_typeof(source_snapshot)='array' AND
   jsonb_typeof(validation)='object'
  );
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='company_contexts'::regclass AND conname='pulse_context_json_check') THEN
  ALTER TABLE company_contexts ADD CONSTRAINT pulse_context_json_check CHECK (jsonb_typeof(structured_context)='object');
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='company_documents'::regclass AND conname='pulse_document_json_check') THEN
  ALTER TABLE company_documents ADD CONSTRAINT pulse_document_json_check CHECK (jsonb_typeof(extracted_metadata)='object');
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='insight_updates'::regclass AND conname='pulse_updates_json_check') THEN
  ALTER TABLE insight_updates ADD CONSTRAINT pulse_updates_json_check CHECK (jsonb_typeof(supporting_data)='array');
 END IF;
END $$;

-- Block writes during validation and installation; existing inconsistencies abort.
LOCK TABLE analysis_runs IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE company_news_analyses IN SHARE ROW EXCLUSIVE MODE;
DO $$ BEGIN
 IF EXISTS (
  SELECT 1 FROM company_news_analyses a JOIN analysis_runs r ON r.id=a.analysis_run_id
  WHERE r.company_id IS NOT NULL AND r.company_id<>a.company_id
 ) THEN
  RAISE EXCEPTION 'Existing analysis company does not match its run' USING ERRCODE='23514';
 END IF;
END $$;

CREATE OR REPLACE FUNCTION pulse_check_analysis_company() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE run_company BIGINT;
BEGIN
 -- SHARE also conflicts with a non-key UPDATE of analysis_runs.company_id.
 SELECT company_id INTO run_company FROM analysis_runs WHERE id=NEW.analysis_run_id FOR SHARE;
 IF run_company IS NOT NULL AND run_company<>NEW.company_id THEN
  RAISE EXCEPTION 'Analysis company must match run company' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE OR REPLACE TRIGGER pulse_analysis_company
 BEFORE INSERT OR UPDATE OF company_id, analysis_run_id ON company_news_analyses
 FOR EACH ROW EXECUTE FUNCTION pulse_check_analysis_company();

CREATE OR REPLACE FUNCTION pulse_check_run_company() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.company_id IS NOT NULL AND EXISTS (
  SELECT 1 FROM company_news_analyses WHERE analysis_run_id=NEW.id AND company_id<>NEW.company_id
 ) THEN
  RAISE EXCEPTION 'Run company conflicts with existing analyses' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE OR REPLACE TRIGGER pulse_run_company
 BEFORE UPDATE OF company_id ON analysis_runs
 FOR EACH ROW EXECUTE FUNCTION pulse_check_run_company();
COMMIT;
