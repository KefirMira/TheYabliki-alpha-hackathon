-- Fully invented fixtures. No rows or identifiers copied from hackathon data.
BEGIN;
INSERT INTO companies(source_id,name,industry,region,revenue,client_status,source_data) VALUES
 ('SYNTH-COMPANY-A','Synthetic Workshop A','Synthetic manufacturing','Test region A',1000.25,'CLIENT','{"fixture":true}'),
 ('SYNTH-COMPANY-B','Synthetic Studio B','Synthetic services','Test region B',2000.50,'PROSPECT','{"fixture":true}');
INSERT INTO persons(source_id,full_name) VALUES ('SYNTH-PERSON-A','Synthetic Person A'),('SYNTH-PERSON-B','Synthetic Person B');
INSERT INTO company_person_links(source_id,company_id,person_id,source_company_id,source_person_id)
SELECT 'SYNTH-LINK-'||suffix,c.id,p.id,c.source_id,p.source_id
FROM (VALUES ('A'),('B')) s(suffix) JOIN companies c ON c.source_id='SYNTH-COMPANY-'||suffix JOIN persons p ON p.source_id='SYNTH-PERSON-'||suffix;
INSERT INTO company_payments(source_id,company_id,source_company_id,payer_source_company_id,amount,payment_count,source_data)
SELECT 'SYNTH-PAYMENT-'||suffix,id,source_id,'SYNTH-EXTERNAL-PAYER',12.50,2,'{"fixture":true}'
FROM (VALUES ('A'),('B')) s(suffix) JOIN companies ON source_id='SYNTH-COMPANY-'||suffix;
COMMIT;
