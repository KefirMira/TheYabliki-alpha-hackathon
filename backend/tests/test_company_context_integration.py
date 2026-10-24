import asyncio
import json
import time

import pytest
from sqlalchemy import event

from repositories.company_repository import CompanyRepository
from services.company_context_service import load_company_context, CompanyContextExternalTransferBlocked
from services.company_analysis_service import CompanyAnalysisService
from test_job_claim_integration import job_database
from test_news_identity_migration import identity_dsn

pytestmark=pytest.mark.integration


async def profile(c):
    data={'_company_profile_csv_v1':{'source':'df_Uid_data_hack','current':{'file_sha256':'a'*64,
        'attributes':{'MAINOKVED_CODE':'62.01','MAINOKVED_NAME':'Synthetic industry',
                      'CL_PRODUCT_LOA_MARK':'1','AMOUNT_WORKERS_FNS_GRADATION':'16-100',
                      'secret':'MUST-NOT-LEAVE-DATABASE'}}}}
    await c.execute("UPDATE companies SET industry='Synthetic industry',revenue=123.45,source_data=$1::jsonb WHERE source_id='SYNTH-COMPANY-A'",json.dumps(data))


async def payments(c, count=5):
    data=json.dumps({'_external_csv_row_v1':{'source':'df_Uid_payment_hack','file_sha256':'b'*64}})
    rows=[]
    for i in range(count):
        # Three incoming rows per five, including a repeated pair; two outgoing.
        beneficiary,payer=[('SYNTH-COMPANY-A','OUTSIDE-1'),('SYNTH-COMPANY-A','OUTSIDE-1'),
                           ('SYNTH-COMPANY-A','OUTSIDE-2'),('OUTSIDE-1','SYNTH-COMPANY-A'),
                           ('OUTSIDE-2','SYNTH-COMPANY-A')][i%5]
        rows.append(('SYNTH-PAY-'+str(i),beneficiary,payer,'df_Uid_payment_hack',data))
    await c.copy_records_to_table('company_payments',records=rows,
        columns=['source_id','source_company_id','payer_source_company_id','source_name','source_data'])


def test_company_context_structural_aggregates_and_read_only(identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            await profile(c)
            await payments(c)
            # Unproven rows must not be used, even with a matching beneficiary.
            await c.execute("INSERT INTO company_payments(source_id,source_company_id,amount,payment_count) VALUES ('SYNTH-IGNORED','SYNTH-COMPANY-A',999999,999)")
            before=await c.fetchval("SELECT md5(string_agg(row_to_json(c)::text,',' ORDER BY id)) FROM companies c")
            async with sessions() as s:
                record=await CompanyRepository(s).get_by_source_id('SYNTH-COMPANY-A')
                context=await load_company_context(s,record)
            structure=context['computed']['payment_structure']
            assert structure['incoming']=={'source_rows':3,'distinct_counterparties':2}
            assert structure['outgoing']=={'source_rows':2,'distinct_counterparties':2}
            assert context['facts']['employee_ranges']['fns']['value']=='16-100'
            assert context['facts']['revenue']['value']=='123.45'
            assert 'MUST-NOT-LEAVE-DATABASE' not in json.dumps(context)
            assert 'OUTSIDE-1' not in json.dumps(context)
            assert await c.fetchval('SELECT count(*) FROM companies')==2
            assert before==await c.fetchval("SELECT md5(string_agg(row_to_json(c)::text,',' ORDER BY id)) FROM companies c")
    asyncio.run(scenario())


def test_company_context_analysis_without_connection_and_cached_history(identity_dsn,bundle_factory):
    async def scenario():
        async with job_database(identity_dsn) as (engine,sessions,c,news):
            await profile(c)
            await payments(c)
            connections=0
            calls=[]
            def checkout(*args):
                nonlocal connections
                connections+=1
            def checkin(*args):
                nonlocal connections
                connections-=1
            event.listen(engine.sync_engine,'checkout',checkout)
            event.listen(engine.sync_engine,'checkin',checkin)
            async def fake(*,company,news):
                assert connections==0
                calls.append(company._ai_context)
                return bundle_factory(news,company.company_id)
            service=CompanyAnalysisService(sessions,fake)
            first=await service.analyze_saved('SYNTH-COMPANY-A',news)
            # Default external analyzer still reuses cached COMPLETED, no context reload/SDK.
            cached=await CompanyAnalysisService(sessions).analyze_saved('SYNTH-COMPANY-A',news)
            assert cached.reused and first.insight_id==cached.insight_id
            await service.analyze_saved('SYNTH-COMPANY-B',news)
            assert len(calls)==2 and calls[0]!=calls[1]
            assert await c.fetchval('SELECT count(*) FROM analysis_runs')==2
            assert await c.fetchval('SELECT count(*) FROM insight_evidence')==4
            assert await c.fetchval('SELECT count(*) FROM news_articles')==1
    asyncio.run(scenario())


def test_company_context_external_block_rolls_back_before_dispatch(identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            service=CompanyAnalysisService(sessions)
            for operation in [service.analyze_saved('SYNTH-COMPANY-A',news),
                              service.analyze('SYNTH-COMPANY-A','Synthetic manual news')]:
                with pytest.raises(CompanyContextExternalTransferBlocked):await operation
            for table in ['analysis_runs','news_analysis_jobs','news_analysis_attempts','company_news_analyses']:
                assert await c.fetchval('SELECT count(*) FROM '+table)==0
            assert await c.fetchval('SELECT count(*) FROM news_articles')==1
    asyncio.run(scenario())


def test_company_context_large_dataset_constant_query_count(identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (engine,sessions,c,_):
            await profile(c)
            await payments(c,100000)
            await c.execute("INSERT INTO companies(source_id,name) SELECT 'SYNTH-BULK-'||i,'Synthetic' FROM generate_series(1,1000) i")
            await c.execute('ANALYZE company_payments')
            statements=[]
            event.listen(engine.sync_engine,'before_cursor_execute',lambda conn,cursor,sql,*args:statements.append(sql))
            async with sessions() as s:
                record=await CompanyRepository(s).get_by_source_id('SYNTH-COMPANY-A')
                statements.clear()
                start=time.perf_counter()
                for _ in range(3):
                    context=await load_company_context(s,record)
                duration=time.perf_counter()-start
            assert len(statements)==3  # One round trip per context, independent of counterparties.
            assert context['computed']['payment_structure']['incoming']['source_rows']==60000
            assert context['computed']['payment_structure']['outgoing']['source_rows']==40000
            assert duration<20
            print(f'CONTEXT_PERF rows=100000 companies=1002 reads=3 sql=3 seconds={duration:.3f}')
    asyncio.run(scenario())
