-- Fully invented fixture covering all remaining application tables.
BEGIN;
INSERT INTO information_sources(name,source_type,url) VALUES ('Synthetic source','USER_DOCUMENT','https://example.invalid/synthetic') RETURNING id AS fixture_source \gset
SELECT id AS fixture_company FROM companies WHERE source_id='SYNTH-COMPANY-B' \gset
INSERT INTO company_contexts(company_id,business_description) VALUES (:fixture_company,'Synthetic business context');
INSERT INTO company_documents(company_id,original_filename,storage_key,processing_status) VALUES (:fixture_company,'synthetic.txt','fixtures/synthetic.txt','COMPLETED');
INSERT INTO news_articles(title,content,input_kind,information_source_id) VALUES ('Synthetic headline','Invented test news','MANUAL',:fixture_source) RETURNING id AS fixture_news \gset
INSERT INTO analysis_runs(company_id,analysis_type,status) VALUES (:fixture_company,'NEWS','COMPLETED') RETURNING id AS fixture_run \gset
INSERT INTO company_news_analyses(analysis_run_id,company_id,news_id,relevance_level,impact_summary) VALUES (:fixture_run,:fixture_company,:fixture_news,'unknown','Synthetic analysis') RETURNING id AS fixture_analysis \gset
INSERT INTO insight_evidence(company_news_analysis_id,information_source_id,evidence_type,evidence_text) VALUES (:fixture_analysis,:fixture_source,'DOCUMENT','Synthetic evidence');
INSERT INTO company_insight_states(company_news_analysis_id,user_key) VALUES (:fixture_analysis,'synthetic-user');
INSERT INTO insight_updates(company_news_analysis_id,verification_status,update_summary) VALUES (:fixture_analysis,'UNVERIFIED','Synthetic update');
COMMIT;
