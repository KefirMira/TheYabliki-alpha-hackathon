-- Entirely invented frontend examples. No CSV or private RAG content is used.
BEGIN;
INSERT INTO companies(source_id,name,industry,region,revenue,revenue_year,client_status)
VALUES ('DEMO-001','Демо: Северная пекарня','Пищевая промышленность','Тестовый регион','12345678.90',2025,'CLIENT'),
       ('DEMO-002','Демо: Мастерская','Производство','Тестовый регион','2000000.01',2025,'PROSPECT'),
       ('DEMO-003','Демо: Пустая история','Услуги','Тестовый регион',NULL,NULL,'PROSPECT');
-- Invented, explicitly reviewed alias for local deterministic matching demonstrations.
INSERT INTO company_verified_names(company_id,name,verified_by,provenance)
SELECT id,'Синтетическая северная пекарня','synthetic-fixture-reviewer','Invented demo alias, not real registry data'
FROM companies WHERE source_id='DEMO-001';
DO $$
DECLARE
 company_key BIGINT; news_key BIGINT; run_key BIGINT; insight_key BIGINT;
 item INTEGER; source_document TEXT := 'synthetic-demo.txt';
 fragment TEXT := 'Полностью синтетический фрагмент для проверки интерфейса. Не является аналитическим доказательством.';
BEGIN
 FOR item IN 1..3 LOOP
  SELECT id INTO company_key FROM companies WHERE source_id = CASE WHEN item < 3 THEN 'DEMO-001' ELSE 'DEMO-002' END;
  INSERT INTO news_articles(title,content,input_kind,source_name,published_at)
  VALUES ('Демо-новость ' || item,'Вымышленная новость для макета интерфейса, сценарий ' || item,'MANUAL','Synthetic demo',TIMESTAMPTZ '2026-01-01 12:00:00+00' + item * INTERVAL '1 day') RETURNING id INTO news_key;
  INSERT INTO analysis_runs(company_id,analysis_type,status,model_name,prompt_version,started_at,finished_at)
  VALUES (company_key,'NEWS','COMPLETED','synthetic-no-llm','demo-v1',TIMESTAMPTZ '2026-01-01 12:00:00+00',TIMESTAMPTZ '2026-01-01 12:00:01+00') RETURNING id INTO run_key;
  INSERT INTO company_news_analyses(analysis_run_id,company_id,news_id,insight_kind,relevance_level,impact_summary,risks,opportunities,recommendations,validation,source_snapshot,created_at)
  VALUES (run_key,company_key,news_key,CASE WHEN item=1 THEN 'risk' WHEN item=2 THEN 'opportunity' ELSE 'information' END,'unknown',
   'Синтетический инсайт ' || item || ': только для проверки frontend.',
   '["Вымышленный риск для демонстрации"]'::jsonb,'["Вымышленная возможность для демонстрации"]'::jsonb,
   '["Не использовать демо-данные для бизнес-решений"]'::jsonb,
   '{"passed":false,"warnings":["Синтетическая фикстура, AI не вызывался"]}'::jsonb,
   jsonb_build_array(jsonb_build_object('id',1,'document',source_document,'page',1,'chunk_id',1,'date','2026-01','synthetic',true)),
   TIMESTAMPTZ '2026-01-01 12:00:00+00' + item * INTERVAL '1 day') RETURNING id INTO insight_key;
  INSERT INTO insight_evidence(company_news_analysis_id,news_id,evidence_type,evidence_text,document_name,document_page,chunk_id)
  VALUES (insight_key,news_key,'DOCUMENT',fragment,source_document,1,1);
 END LOOP;
END $$;
COMMIT;
