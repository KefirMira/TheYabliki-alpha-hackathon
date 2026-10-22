\set ON_ERROR_STOP on
BEGIN;
CREATE FUNCTION pg_temp.assert_true(ok boolean, msg text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN IF ok IS DISTINCT FROM TRUE THEN RAISE EXCEPTION '%',msg; END IF; END $$;
CREATE FUNCTION pg_temp.reject(statement text, expected_state text, expected_constraint text DEFAULT NULL, expected_message text DEFAULT NULL) RETURNS void LANGUAGE plpgsql AS $$
DECLARE caught boolean := false; actual_constraint text; actual_message text;
BEGIN
 BEGIN EXECUTE statement;
 EXCEPTION WHEN OTHERS THEN
  IF SQLSTATE<>expected_state THEN RAISE; END IF;
  GET STACKED DIAGNOSTICS actual_constraint = CONSTRAINT_NAME, actual_message = MESSAGE_TEXT;
  IF expected_constraint IS NOT NULL AND actual_constraint IS DISTINCT FROM expected_constraint THEN
   RAISE EXCEPTION 'Expected constraint %, got % for %',expected_constraint,actual_constraint,statement;
  END IF;
  IF expected_message IS NOT NULL AND actual_message IS DISTINCT FROM expected_message THEN
   RAISE EXCEPTION 'Expected message %, got %',expected_message,actual_message;
  END IF;
  caught := true;
 END;
 IF NOT caught THEN RAISE EXCEPTION 'Unexpected acceptance: %',statement; END IF;
END $$;
SELECT pg_temp.assert_true((SELECT count(*)=13 FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'),'Expected 13 tables');
SELECT pg_temp.assert_true((SELECT count(*)=2 FROM companies),'companies seed');
SELECT pg_temp.assert_true((SELECT count(*)=2 FROM persons),'persons seed');
SELECT pg_temp.assert_true((SELECT count(*)=2 FROM company_person_links),'links seed');
SELECT pg_temp.assert_true((SELECT count(*)=2 FROM company_payments),'payments seed');

DO $$ DECLARE tbl text; n bigint; BEGIN
 FOREACH tbl IN ARRAY ARRAY['information_sources','company_contexts','company_documents','news_articles','analysis_runs','company_news_analyses','insight_evidence','company_insight_states','insight_updates'] LOOP
  EXECUTE format('SELECT count(*) FROM %I',tbl) INTO n;
  PERFORM pg_temp.assert_true(n=1,'Expected one synthetic fixture in '||tbl);
 END LOOP;
END $$;

INSERT INTO information_sources(name,source_type) VALUES ('Audit PDF','BANK_ANALYTICS') RETURNING id AS source_id \gset
INSERT INTO news_articles(title,content,input_kind,submitted_by_user_key) VALUES ('Test news','Synthetic test, no LLM','MANUAL','audit-user') RETURNING id AS news_id \gset
SELECT id AS company_id FROM companies WHERE source_id='SYNTH-COMPANY-A' \gset
SELECT id AS other_id FROM companies WHERE source_id='SYNTH-COMPANY-B' \gset
INSERT INTO analysis_runs(company_id,analysis_type,status) VALUES (:company_id,'NEWS','COMPLETED') RETURNING id AS run_id \gset
INSERT INTO company_news_analyses(analysis_run_id,company_id,news_id,relevance_level,impact_summary,risks,opportunities,recommendations,validation,source_snapshot)
VALUES (:run_id,:company_id,:news_id,'high','Synthetic summary','["Risk"]','["Opportunity"]','["Action"]','{"passed":true,"warnings":[]}','[{"id":1,"document":"audit.pdf","page":1,"score":0.42}]') RETURNING id AS analysis_id \gset
INSERT INTO insight_evidence(company_news_analysis_id,information_source_id,evidence_type,evidence_text,document_name,document_page,chunk_id)
VALUES (:analysis_id,:source_id,'PDF','Synthetic evidence','audit.pdf',1,1);
SELECT pg_temp.assert_true((SELECT relevance_level='high' AND impact_summary='Synthetic summary' AND risks='["Risk"]'::jsonb AND opportunities='["Opportunity"]'::jsonb AND recommendations='["Action"]'::jsonb AND validation='{"passed":true,"warnings":[]}'::jsonb AND source_snapshot->0->>'document'='audit.pdf' FROM company_news_analyses WHERE id=:analysis_id),'AI round trip');

SELECT pg_temp.reject(format('UPDATE company_news_analyses SET company_id=%s WHERE id=%s',:other_id,:analysis_id),'23514',NULL,'Analysis company must match run company');
SELECT pg_temp.reject(format('UPDATE analysis_runs SET company_id=%s WHERE id=%s',:other_id,:run_id),'23514',NULL,'Run company conflicts with existing analyses');
SELECT pg_temp.reject(format('UPDATE company_news_analyses SET news_id=-1 WHERE id=%s',:analysis_id),'23503','company_news_analyses_news_id_fkey');
SELECT pg_temp.reject(format('UPDATE company_news_analyses SET relevance_level=''invalid'' WHERE id=%s',:analysis_id),'23514','pulse_levels_check');
SELECT pg_temp.reject(format('UPDATE company_news_analyses SET risks=''{}'' WHERE id=%s',:analysis_id),'23514','pulse_analysis_json_check');
SELECT pg_temp.reject(format('UPDATE company_news_analyses SET validation=''[]'' WHERE id=%s',:analysis_id),'23514','pulse_analysis_json_check');
-- Exercise every new JSONB field and every level field.
DO $$ DECLARE col text; aid bigint; BEGIN
 SELECT max(id) INTO aid FROM company_news_analyses;
 FOREACH col IN ARRAY ARRAY['facts','risks','opportunities','recommendations','scenarios','source_snapshot'] LOOP
  PERFORM pg_temp.reject(format('UPDATE company_news_analyses SET %I=''{}'' WHERE id=%s',col,aid),'23514','pulse_analysis_json_check');
 END LOOP;
 FOREACH col IN ARRAY ARRAY['insight_kind','relevance_level','impact_level','evidence_strength'] LOOP
  PERFORM pg_temp.reject(format('UPDATE company_news_analyses SET %I=''invalid'' WHERE id=%s',col,aid),'23514','pulse_levels_check');
 END LOOP;
END $$;
SELECT pg_temp.reject(format('DELETE FROM companies WHERE id=%s',:company_id),'23503');
INSERT INTO company_contexts(company_id) VALUES (:company_id) RETURNING id AS context_id \gset
SELECT pg_temp.reject(format('INSERT INTO company_contexts(company_id) VALUES (%s)',:company_id),'23505','company_contexts_company_id_key');
SELECT pg_temp.reject(format('UPDATE company_contexts SET structured_context=''[]'' WHERE id=%s',:context_id),'23514','pulse_context_json_check');
SELECT pg_temp.reject(format('INSERT INTO company_documents(company_id,original_filename,storage_key,size_bytes) VALUES (%s,''test'',''test'',-1)',:company_id),'23514','company_documents_size_check');
SELECT pg_temp.reject('INSERT INTO information_sources(name,source_type) VALUES (''bad'',''INVALID'')','23514','information_sources_type_check');
INSERT INTO company_insight_states(company_news_analysis_id,user_key,is_favorite) VALUES (:analysis_id,'audit-user',true);
SELECT pg_temp.reject(format('INSERT INTO company_insight_states(company_news_analysis_id,user_key) VALUES (%s,''audit-user'')',:analysis_id),'23505','company_insight_states_company_news_analysis_id_user_key_key');
INSERT INTO insight_updates(company_news_analysis_id,verification_status,update_summary) VALUES (:analysis_id,'UNVERIFIED','Test');
SELECT pg_temp.reject(format('INSERT INTO insight_updates(company_news_analysis_id,verification_status,update_summary) VALUES (%s,''INVALID'',''Test'')',:analysis_id),'23514','insight_updates_status_check');
SELECT pg_temp.reject(format('INSERT INTO insight_updates(company_news_analysis_id,verification_status,update_summary,supporting_data) VALUES (%s,''UNVERIFIED'',''Test'',''{}'')',:analysis_id),'23514','pulse_updates_json_check');
SELECT pg_temp.reject(format('INSERT INTO company_documents(company_id,original_filename,storage_key,extracted_metadata) VALUES (%s,''test'',''test'',''[]'')',:company_id),'23514','pulse_document_json_check');
-- All declared FKs are validated; test each with a nonexistent parent.
DO $$ DECLARE fk record; row_id bigint; empty_run_id bigint; BEGIN
 -- This run has no results, so its company FK can fail independently of the
 -- cross-table company-consistency trigger.
 INSERT INTO analysis_runs(analysis_type) VALUES ('FK_TEST') RETURNING id INTO empty_run_id;
 FOR fk IN SELECT conrelid::regclass AS tbl, a.attname AS col, c.conname, c.convalidated
 FROM pg_constraint c JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=c.conkey[1]
 WHERE c.contype='f' AND c.connamespace='public'::regnamespace LOOP
  PERFORM pg_temp.assert_true(fk.convalidated,'Unvalidated FK: '||fk.conname);
  EXECUTE format('SELECT id FROM %s ORDER BY id DESC LIMIT 1',fk.tbl) INTO row_id;
  PERFORM pg_temp.assert_true(row_id IS NOT NULL,'Missing fixture for FK: '||fk.conname);
  IF fk.tbl::text='analysis_runs' THEN
   row_id := empty_run_id;
  END IF;
  IF fk.tbl::text='company_news_analyses' AND fk.col='company_id' THEN
   -- Remove the run-company requirement first to isolate the company FK.
   UPDATE analysis_runs SET company_id=NULL WHERE id=(SELECT analysis_run_id FROM company_news_analyses WHERE id=row_id);
  END IF;
  PERFORM pg_temp.reject(format('UPDATE %s SET %I=-1 WHERE id=%s',fk.tbl,fk.col,row_id),'23503',fk.conname);
 END LOOP;
END $$;
-- Nullable run company retains the original multi-company semantics.
UPDATE analysis_runs SET company_id=NULL WHERE id=:run_id;
UPDATE company_news_analyses SET company_id=:other_id WHERE id=:analysis_id;
ROLLBACK;
\echo PASS: seed, 13 tables, AI round trip, constraints and company consistency
