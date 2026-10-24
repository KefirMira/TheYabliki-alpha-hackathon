import asyncio
import json
import time

import pytest
from sqlalchemy.exc import DBAPIError

from company_import.validation import ImportProblem
from dataset_import.storage import apply_audit
from dataset_import.validation import NAMESPACE, audit_file
from test_dataset_import import write_rows
from test_company_import_integration import marked_target
from test_job_claim_integration import job_database, identity_dsn

pytestmark = pytest.mark.integration
TABLES = {'payments':'company_payments', 'links':'company_person_links'}


async def snapshots(c, tables):
    return [await c.fetch(f'SELECT row_to_json(t)::text FROM public.{table} t ORDER BY id') for table in tables]


@pytest.mark.parametrize('kind', ['payments','links'])
def test_lossless_repeat_unknown_identifiers_and_protected_history(tmp_path, identity_dsn, kind):
    async def scenario():
        async with job_database(identity_dsn) as (engine, _, c, news):
            url,name=await marked_target(c,engine)
            company=await c.fetchval("SELECT id FROM companies WHERE source_id='SYNTH-COMPANY-A'")
            await c.execute("INSERT INTO persons(source_id,full_name) VALUES('OPAQUE-F','Synthetic existing person')")
            run=await c.fetchval("INSERT INTO analysis_runs(company_id,analysis_type,status) VALUES($1,'NEWS','COMPLETED') RETURNING id",company)
            insight=await c.fetchval('INSERT INTO company_news_analyses(analysis_run_id,company_id,news_id) VALUES($1,$2,$3) RETURNING id',run,company,news)
            await c.execute("INSERT INTO insight_evidence(company_news_analysis_id,evidence_type,evidence_text) VALUES($1,'DOCUMENT','Synthetic preserved evidence')",insight)
            protected=['companies','persons','analysis_runs','company_news_analyses','insight_evidence','news_articles']
            before=await snapshots(c,protected)
            if kind=='payments':
                row=['SYNTH-COMPANY-A','SYNTH-OUTSIDE','123.40','2']
                rows=[row,row,row[:2]+['456.70','3'],['SYNTH-UNKNOWN','SYNTH-COMPANY-B','0','0']]
            else:
                row=['OPAQUE-F','','','SYNTH-COMPANY-A']
                rows=[row,row,['OPAQUE-F','Synthetic city','Opaque label','SYNTH-COMPANY-A'],['UNKNOWN-F','','','UNKNOWN-U']]
            path=write_rows(tmp_path/'synthetic.csv',kind,rows)
            audit=audit_file(path,kind)
            result=await apply_audit(audit,url,name)
            assert result=={'created':4,'unchanged':0,'updated':0}
            records=await c.fetch(f'SELECT * FROM {TABLES[kind]} ORDER BY id')
            assert [r['company_id'] for r in records]==[company,company,company,None]
            for ordinal,record in enumerate(records,1):
                metadata=json.loads(record['source_data'])[NAMESPACE]
                assert metadata['record_number']==ordinal and metadata['line']==ordinal+1
                assert metadata['attributes']==dict(zip(audit_file_headers(kind),rows[ordinal-1]))
                assert metadata['file_sha256']==audit.file_hash and metadata['importer_version']=='1.19.0b'
                assert metadata['filename']=='synthetic.csv'
                if kind=='payments':
                    assert record['currency'] is record['payment_date'] is record['period_start'] is record['period_end'] is None
                else:
                    assert record['person_id'] is record['role'] is record['relation_type'] is None
            imported_before=await snapshots(c,[TABLES[kind]])
            assert await apply_audit(audit,url,name)=={'created':0,'unchanged':4,'updated':0}
            renamed=tmp_path/'renamed.csv';renamed.write_bytes(path.read_bytes())
            assert (await apply_audit(audit_file(renamed,kind),url,name))['unchanged']==4
            assert await snapshots(c,[TABLES[kind]])==imported_before
            assert await snapshots(c,protected)==before
    asyncio.run(scenario())


def audit_file_headers(kind):
    from dataset_import.validation import HEADERS
    return HEADERS[kind]


def test_two_independent_connections_and_snapshot_admission(tmp_path, identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (engine,_,c,_):
            url,name=await marked_target(c,engine)
            path=write_rows(tmp_path/'synthetic.csv','payments',[['SYNTH-COMPANY-A','OUT','1.20','2']]*1100)
            audit=audit_file(path,'payments')
            result=await asyncio.gather(apply_audit(audit,url,name),apply_audit(audit,url,name))
            assert sum(r['created'] for r in result)==1100 and sum(r['unchanged'] for r in result)==1100
            assert await c.fetchval('SELECT count(*) FROM company_payments')==1100
            other=audit_file(write_rows(tmp_path/'different.csv','payments',[['A','B','2','3']]),'payments')
            with pytest.raises(ImportProblem,match='NEW_SNAPSHOT_REQUIRES_SEPARATE_DATABASE'):
                await apply_audit(other,url,name)
            assert await c.fetchval('SELECT count(*) FROM company_payments')==1100
    asyncio.run(scenario())


@pytest.mark.parametrize('kind', ['payments','links'])
def test_rollback_after_completed_first_batch(tmp_path, identity_dsn, kind):
    async def scenario():
        async with job_database(identity_dsn) as (engine,_,c,_):
            url,name=await marked_target(c,engine)
            table=TABLES[kind]
            await c.execute(f"""CREATE FUNCTION synthetic_dataset_fail() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN IF NEW.source_company_id='SYNTH-FAIL' THEN
                RAISE EXCEPTION 'Synthetic failure' USING ERRCODE='23514'; END IF; RETURN NEW; END $$;
                CREATE TRIGGER synthetic_dataset_fail BEFORE INSERT ON {table}
                FOR EACH ROW EXECUTE FUNCTION synthetic_dataset_fail()""")
            row=['SYNTH-COMPANY-A','OUT','1.20','2'] if kind=='payments' else ['F','','','SYNTH-COMPANY-A']
            fail=['SYNTH-FAIL','OUT','1.20','2'] if kind=='payments' else ['F','','','SYNTH-FAIL']
            audit=audit_file(write_rows(tmp_path/'synthetic.csv',kind,[row]*1000+[fail]),kind)
            before=await snapshots(c,['companies','analysis_runs','company_news_analyses','insight_evidence'])
            with pytest.raises(DBAPIError) as error:
                await apply_audit(audit,url,name)
            assert error.value.orig.sqlstate=='23514'
            assert await c.fetchval(f'SELECT count(*) FROM {table}')==0
            assert await snapshots(c,['companies','analysis_runs','company_news_analyses','insight_evidence'])==before
    asyncio.run(scenario())


def test_marker_and_existing_row_conflict(tmp_path, identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (engine,_,c,_):
            name=await c.fetchval('SELECT current_database()')
            url=engine.url.render_as_string(hide_password=False)
            audit=audit_file(write_rows(tmp_path/'synthetic.csv','payments',[['A','B','1','1']]),'payments')
            with pytest.raises(ImportProblem,match='ISOLATED_DATABASE_MARKER_REQUIRED'):
                await apply_audit(audit,url,name)
            await marked_target(c,engine)
            await apply_audit(audit,url,name)
            await c.execute('UPDATE company_payments SET payment_count=42')
            before=await snapshots(c,['company_payments'])
            with pytest.raises(ImportProblem,match='EXISTING_SOURCE_ROW_CONFLICT'):
                await apply_audit(audit,url,name)
            assert await snapshots(c,['company_payments'])==before
    asyncio.run(scenario())


def test_changed_file_after_inserts_rolls_back(tmp_path, identity_dsn, monkeypatch):
    from dataset_import import storage
    async def scenario():
        async with job_database(identity_dsn) as (engine,_,c,_):
            url,name=await marked_target(c,engine)
            path=write_rows(tmp_path/'synthetic.csv','payments',[['A','B','1','1']])
            audit=audit_file(path,'payments')
            original=storage.batches
            def changed_file(current):
                yield from original(current)
                path.write_bytes(path.read_bytes()+b'\n')
            monkeypatch.setattr(storage,'batches',changed_file)
            with pytest.raises(ImportProblem,match='FILE_CHANGED_DURING_IMPORT'):
                await storage.apply_audit(audit,url,name)
            assert await c.fetchval('SELECT count(*) FROM company_payments')==0
    asyncio.run(scenario())


def test_concurrent_different_snapshots_and_later_company_resolution(tmp_path, identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (engine,_,c,_):
            url,name=await marked_target(c,engine)
            audits=[audit_file(write_rows(tmp_path/f'synthetic-{i}.csv','payments',
                    [[f'OUTSIDE-{i}','PAYER','1','1']]),'payments') for i in range(2)]
            result=await asyncio.gather(*(apply_audit(a,url,name) for a in audits),return_exceptions=True)
            assert sum(isinstance(r,dict) for r in result)==1
            assert [str(r) for r in result if isinstance(r,ImportProblem)]==['NEW_SNAPSHOT_REQUIRES_SEPARATE_DATABASE']
            winner=next(i for i,r in enumerate(result) if isinstance(r,dict))
            assert await c.fetchval('SELECT count(*) FROM company_payments')==1
            await c.execute("INSERT INTO companies(source_id,name) VALUES($1,'Synthetic late company')",f'OUTSIDE-{winner}')
            assert (await apply_audit(audits[winner],url,name))['unchanged']==1
            assert await c.fetchval('SELECT company_id FROM company_payments') is None
    asyncio.run(scenario())


@pytest.mark.parametrize('kind', ['payments','links'])
def test_large_synthetic_import_performance(tmp_path, identity_dsn, kind):
    async def scenario():
        async with job_database(identity_dsn) as (engine,_,c,_):
            url,name=await marked_target(c,engine)
            count=50000
            def rows():
                for i in range(count):
                    if kind=='payments':
                        yield ['SYNTH-COMPANY-A',f'SYNTH-OUT-{i%100}',f'{i%500}.20',str(i%10)]
                    else:
                        yield [f'OPAQUE-{i%100}','Synthetic city','','SYNTH-COMPANY-A']
            path=write_rows(tmp_path/'large-synthetic.csv',kind,rows())
            start=time.perf_counter();audit=audit_file(path,kind);dry=time.perf_counter()-start
            start=time.perf_counter();result=await apply_audit(audit,url,name);first=time.perf_counter()-start
            start=time.perf_counter();replay=await apply_audit(audit,url,name);repeat=time.perf_counter()-start
            assert result['created']==count and replay['unchanged']==count and replay['created']==0
            assert await c.fetchval(f'SELECT count(*) FROM {TABLES[kind]}')==count
            print(f'PERF kind={kind} synthetic_rows={count} dry_seconds={dry:.3f} first_seconds={first:.3f} repeat_seconds={repeat:.3f} rows_per_second={count/first:.1f}')
    asyncio.run(scenario())
