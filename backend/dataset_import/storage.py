"""Bounded JSON batches, immutable source rows, one transaction per file."""
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from company_import.storage import MARKER, target_url
from company_import.validation import ImportProblem
from .validation import NAMESPACE, SOURCES, batches, fingerprint

TABLES = {'payments': 'company_payments', 'links': 'company_person_links'}
COMMON = 'source_id text,source_company_id text,source_data jsonb'
PAYMENT_FIELDS = ',payer_source_company_id text,amount numeric(18,2),payment_count bigint'
LINK_FIELDS = ',source_person_id text,city_name text,rc_name text'


async def apply_audit(audit, url, expected_database):
    url = target_url(url, expected_database)
    if audit.rejected_rows:
        raise ImportProblem('INVALID_ROWS_BLOCK_IMPORT')
    if not audit.rows:
        raise ImportProblem('NO_ROWS')
    if fingerprint(audit.path) != audit.file_hash:
        raise ImportProblem('FILE_CHANGED_AFTER_DRY_RUN')
    table = TABLES[audit.kind]  # Closed constants, never CSV or CLI SQL identifiers.
    fields = COMMON + (PAYMENT_FIELDS if audit.kind == 'payments' else LINK_FIELDS)
    if audit.kind == 'payments':
        columns = 'payer_source_company_id,amount,payment_count'
        values = 'b.payer_source_company_id,b.amount,b.payment_count'
        mismatch = '''p.payer_source_company_id IS DISTINCT FROM b.payer_source_company_id
            OR p.amount IS DISTINCT FROM b.amount OR p.payment_count IS DISTINCT FROM b.payment_count
            OR p.currency IS NOT NULL OR p.payment_date IS NOT NULL OR p.period_start IS NOT NULL
            OR p.period_end IS NOT NULL OR p.payment_type IS NOT NULL OR p.description IS NOT NULL'''
    else:
        columns = 'source_person_id,city_name,rc_name'
        values = 'b.source_person_id,b.city_name,b.rc_name'
        mismatch = '''p.source_person_id IS DISTINCT FROM b.source_person_id
            OR p.city_name IS DISTINCT FROM b.city_name OR p.rc_name IS DISTINCT FROM b.rc_name
            OR p.person_id IS NOT NULL OR p.role IS NOT NULL OR p.relation_type IS NOT NULL
            OR p.start_date IS NOT NULL OR p.end_date IS NOT NULL'''
    batch_sql = 'SELECT * FROM jsonb_to_recordset(CAST(:payload AS jsonb)) AS x(' + fields + ')'
    insert_sql = f'''WITH batch AS ({batch_sql}), inserted AS (
        INSERT INTO public.{table}(source_id,company_id,source_company_id,source_name,source_data,{columns})
        SELECT b.source_id,c.id,b.source_company_id,:source,b.source_data,{values}
        FROM batch b LEFT JOIN public.companies c ON c.source_id=b.source_company_id
        ON CONFLICT(source_id) DO NOTHING RETURNING id)
        SELECT count(*) FROM inserted'''
    verify_sql = f'''WITH batch AS ({batch_sql}) SELECT count(*) FROM batch b
        LEFT JOIN public.{table} p ON p.source_id=b.source_id
        LEFT JOIN public.companies c ON c.id=p.company_id
        WHERE p.id IS NULL OR p.source_company_id IS DISTINCT FROM b.source_company_id
        OR p.source_name IS DISTINCT FROM :source
        OR ((p.source_data -> :namespace) - 'filename') IS DISTINCT FROM ((b.source_data -> :namespace) - 'filename')
        OR (p.company_id IS NOT NULL AND c.source_id IS DISTINCT FROM p.source_company_id)
        OR ({mismatch})'''
    engine = create_async_engine(url, poolclass=NullPool, hide_parameters=True,
                                 connect_args={'timeout':5, 'command_timeout':60})
    created = processed = 0
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SET LOCAL lock_timeout='10s'"))
            await connection.execute(text("SET LOCAL statement_timeout='60s'"))
            target = (await connection.execute(text('''SELECT current_database() AS name,
                shobj_description(oid,'pg_database') AS marker FROM pg_catalog.pg_database
                WHERE datname=current_database()'''))).mappings().one()
            if target['name'] != expected_database or target['marker'] != MARKER:
                raise ImportProblem('ISOLATED_DATABASE_MARKER_REQUIRED')
            # Serialize snapshot admission, including concurrent *different* files.
            # Existing UNIQUE(source_id) remains the final per-row race protection.
            await connection.execute(text(f'LOCK TABLE public.{table} IN SHARE ROW EXCLUSIVE MODE'))
            wrong_snapshot = await connection.scalar(text(f'''SELECT EXISTS(SELECT 1 FROM public.{table}
                WHERE source_data ? :namespace AND
                (jsonb_typeof(source_data -> :namespace) IS DISTINCT FROM 'object'
                 OR source_data -> :namespace ->> 'file_sha256' IS DISTINCT FROM :file_hash
                 OR source_data -> :namespace ->> 'source' IS DISTINCT FROM :source))'''),
                {'namespace':NAMESPACE,'file_hash':audit.file_hash,'source':SOURCES[audit.kind]})
            if wrong_snapshot:
                raise ImportProblem('NEW_SNAPSHOT_REQUIRES_SEPARATE_DATABASE')
            for batch in batches(audit):
                params = {'payload':json.dumps(batch, ensure_ascii=False), 'source':SOURCES[audit.kind], 'namespace':NAMESPACE}
                created += await connection.scalar(text(insert_sql),params)
                if await connection.scalar(text(verify_sql),params):
                    raise ImportProblem('EXISTING_SOURCE_ROW_CONFLICT')
                processed += len(batch)
            if processed != audit.rows or fingerprint(audit.path) != audit.file_hash:
                raise ImportProblem('FILE_CHANGED_DURING_IMPORT')
        return {'created':created,'unchanged':processed-created,'updated':0}
    finally:
        await engine.dispose()
