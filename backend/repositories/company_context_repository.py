"""One bounded projection and indexed structural aggregates; no amounts or raw rows."""
from sqlalchemy import text

CSV_FIELDS = (
    'MAINOKVED_CODE', 'MAINOKVED_NAME', 'REGION', 'AMOUNT_WORKERS_FNS_GRADATION',
    'AMOUNT_WORKERS_SPARK_GRADATION', 'CL_PRODUCT_RKO_MARK', 'CL_PRODUCT_GAR_MARK',
    'CL_PRODUCT_LOA_MARK', 'CL_PRODUCT_LEA_MARK', 'CL_PRODUCT_DEP_MARK',
    'CL_PRODUCT_ZPP_MARK', 'FACTORING_MARK', 'FTS_FLAG',
)
# SQL identifiers/JSON keys come exclusively from the fixed whitelist above.
CSV_PROJECTION = ','.join(
    "'"+key+"',CASE WHEN octet_length(c.source_data #>> '{_company_profile_csv_v1,current,attributes,"+key+"}')<=1024 "
    "THEN c.source_data #>> '{_company_profile_csv_v1,current,attributes,"+key+"}' END"
    for key in CSV_FIELDS)
PAYMENT_ORIGIN = """p.source_name='df_Uid_payment_hack'
    AND p.source_data #>> '{_external_csv_row_v1,source}'='df_Uid_payment_hack'
    AND p.source_data #>> '{_external_csv_row_v1,file_sha256}' ~ '^[0-9a-f]{64}$'"""
CONTEXT_SQL = f"""
SELECT CASE WHEN length(c.industry)<=320 THEN c.industry END AS industry,
       CASE WHEN length(c.region)<=128 THEN c.region END AS region,
       c.revenue,c.revenue_year,c.client_status,
       coalesce(c.source_data #>> '{{_company_profile_csv_v1,source}}'='df_Uid_data_hack'
           AND jsonb_typeof(c.source_data #> '{{_company_profile_csv_v1,current,attributes}}')='object'
           AND c.source_data #>> '{{_company_profile_csv_v1,current,file_sha256}}' ~ '^[0-9a-f]{{64}}$',false) AS csv_origin,
       jsonb_build_object({CSV_PROJECTION}) AS csv_fields,
       incoming.source_rows AS incoming_rows,incoming.counterparties AS incoming_counterparties,
       outgoing.source_rows AS outgoing_rows,outgoing.counterparties AS outgoing_counterparties,
       EXISTS(SELECT 1 FROM public.company_payments p WHERE {PAYMENT_ORIGIN}) AS snapshot_present
FROM public.companies c
CROSS JOIN LATERAL (
 SELECT count(*) AS source_rows,count(DISTINCT p.payer_source_company_id) AS counterparties
 FROM public.company_payments p WHERE p.source_company_id=c.source_id AND {PAYMENT_ORIGIN}
) incoming
CROSS JOIN LATERAL (
 SELECT count(*) AS source_rows,count(DISTINCT p.source_company_id) AS counterparties
 FROM public.company_payments p WHERE p.payer_source_company_id=c.source_id AND {PAYMENT_ORIGIN}
) outgoing
WHERE c.id=:company_id AND c.source_id=:source_id
"""


class CompanyContextRepository:
    def __init__(self, session):
        self.session = session

    async def load(self, company_id, source_id):
        result = await self.session.execute(text(CONTEXT_SQL), {'company_id':company_id,'source_id':source_id})
        row = result.mappings().one_or_none()
        return dict(row) if row is not None else None
