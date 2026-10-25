"""12 fixed scenarios x 3 fresh databases; real ACL/jobs, only fixed local fake SDK."""
import asyncio
import copy
import json
import subprocess
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event
from evaluation import quality
from evaluation.runner import write_json
from services.synthetic_news_execution_service import SyntheticNewsExecutionService, LocalFakeAnalysisSDK
from synthetic_actor_fixture import job_database, add_actor
from test_news_identity_migration import identity_dsn

pytestmark=pytest.mark.integration


async def execute_case(dsn, case, data):
    async with job_database(dsn) as (_,sessions,c,news):
        active=0
        def checkout(*args):
            nonlocal active
            active+=1
        def checkin(*args):
            nonlocal active
            active-=1
        event.listen(sessions.kw['bind'].sync_engine,'checkout',checkout)
        event.listen(sessions.kw['bind'].sync_engine,'checkin',checkin)
        attrs={'MAINOKVED_CODE':'46.71' if case['industry'] else None,'MAINOKVED_NAME':case['industry'],
            'CL_PRODUCT_LOA_MARK':'1' if case['loan_flag'] else '0',
            'CL_PRODUCT_DEP_MARK':'1' if case['deposit_flag'] else '0',
            'AMOUNT_WORKERS_FNS_GRADATION':'16-100'}
        provenance={'_company_profile_csv_v1':{'source':'df_Uid_data_hack',
            'current':{'attributes':attrs,'file_sha256':'a'*64}}}
        await c.execute("UPDATE companies SET industry=$1,region='SYNTHETIC-REGION-A',source_data=$2::jsonb WHERE source_id='SYNTH-COMPANY-A'",
            case['industry'],json.dumps(provenance))
        await c.execute("UPDATE companies SET industry='SYNTHETIC-INDUSTRY-B',region='SYNTHETIC-REGION-B' WHERE source_id='SYNTH-COMPANY-B'")
        await c.execute('UPDATE news_articles SET content=$1 WHERE id=$2',data['news'],news)
        _,token=await add_actor(c,news,('SYNTH-COMPANY-A',))
        _,other_token=await add_actor(c,news,('SYNTH-COMPANY-B',))
        _,no_news_token=await add_actor(c,news,('SYNTH-COMPANY-A',),grant=False)
        sdk=LocalFakeAnalysisSDK()
        inputs=[]
        async def complete(payload):
            assert active==0
            inputs.append(copy.deepcopy(payload))
            return json.dumps(quality.draft(case),ensure_ascii=False)
        sdk.complete=AsyncMock(side_effect=complete)
        def service(actor):
            return SyntheticNewsExecutionService(sessions,corpus_loader=lambda:quality.source_corpus(case,data),
                confirm_synthetic=True,fake_sdk=sdk,session_token=actor)
        # Cross-user denial must precede both first claim and cached response.
        for actor in (other_token,no_news_token):
            denied=await service(actor).analyze_saved('SYNTH-COMPANY-A',news)
            assert denied.status=='REJECTED' and denied.error_code=='ACCESS_DENIED'
        assert await c.fetchval('SELECT count(*) FROM news_analysis_attempts')==0
        runner=service(token)
        report=await runner.analyze_saved('SYNTH-COMPANY-A',news)
        assert report.status==case['expected_status'],(case['id'],report.error_code)
        trace=report.orchestration
        actions=[e.decision.action for e in trace.events if e.tool=='DECIDE']
        assert actions==case['expected_actions'],case['id']
        assert trace.corrections==case['corrections'] and trace.reviews==case['reviews']
        assert trace.decisions<=3 and trace.searches<=1 and trace.drafts<=1
        assert report.paid_calls==trace.paid_calls==0
        assert report.preparation.external_transfer_allowed is False
        assert all(e.observation.source_support=='UNKNOWN' for e in trace.events if e.observation)
        if inputs:
            context=inputs[0]['company_source_assertions']
            facts=context['facts']
            assert facts['product_and_activity_flags']['loan_product']['value']==case['loan_flag']
            assert facts['product_and_activity_flags']['deposit']['value']==case['deposit_flag']
            assert facts.get('industry',{}).get('value')==case['industry']
            assert 'SYNTHETIC-REGION-B' not in json.dumps(inputs,ensure_ascii=False)
        checks=quality.correction_checks(case,report)
        saved_evidence=[]
        if report.result:
            assert checks['no_new_claims'] is True
            stored=json.loads(await c.fetchval('SELECT validation::text FROM company_news_analyses'))
            assert stored['orchestration']==trace.model_dump(mode='json') and stored['passed'] is False
            assert stored['financial_review']['financial_correctness']=='UNKNOWN'
            saved_evidence=[dict(row) for row in await c.fetch('SELECT document_name,document_page,chunk_id,document_date,evidence_text FROM insight_evidence ORDER BY id')]
            allowed={(x['source'],x['page'],x['chunk_id'],x['text'],x.get('date')) for x in quality.source_corpus(case,data)}
            assert all((e['document_name'],e['document_page'],e['chunk_id'],e['evidence_text'],
                e['document_date'].isoformat() if e['document_date'] else None) in allowed for e in saved_evidence)
            assert len(saved_evidence)==len(report.result.analysis.sources)
            if case['id']=='Q05':assert len(saved_evidence)==1
            if case['id']=='Q10':assert any(f.code=='CITATION_ENTAILMENT_UNKNOWN' for f in report.financial_review.findings)
        else:
            assert await c.fetchval('SELECT count(*) FROM company_news_analyses')==0
            assert await c.fetchval('SELECT count(*) FROM insight_evidence')==0
            assert await c.fetchval('SELECT response_payload IS NULL FROM news_analysis_attempts')
        call_count=sdk.complete.await_count
        repeated=await runner.analyze_saved('SYNTH-COMPANY-A',news)
        assert repeated.status==('REUSED' if report.result else 'CONFLICT')
        assert sdk.complete.await_count==call_count
        if report.result:assert repeated.result==report.result
        for actor in (other_token,no_news_token):
            denied=await service(actor).analyze_saved('SYNTH-COMPANY-A',news)
            assert denied.status=='REJECTED' and denied.result is None and denied.fake_calls==0
        assert await c.fetchval('SELECT count(*) FROM news_analysis_attempts')==1
        independent_b=False
        if case['id']=='Q02':
            other=await service(other_token).analyze_saved('SYNTH-COMPANY-B',news)
            assert other.status=='COMPLETED' and other.result.insight_id!=report.result.insight_id
            assert other.result.analysis.company_id=='SYNTH-COMPANY-B'
            assert 'SYNTHETIC-REGION-A' not in json.dumps(inputs[-1],ensure_ascii=False)
            assert inputs[-1]['company_source_assertions']['facts']['region']['value']=='SYNTHETIC-REGION-B'
            denied=await runner.analyze_saved('SYNTH-COMPANY-B',news)
            assert denied.status=='REJECTED' and denied.result is None
            assert sdk.complete.await_count==2
            assert await c.fetchval('SELECT count(*) FROM news_analysis_attempts')==2
            independent_b=True
        canonical=quality.canonical_execution(report)
        canonical['evidence']=[{**e,'document_date':str(e['document_date']) if e['document_date'] else None} for e in saved_evidence]
        # Keep complete audit hashes in raw reports; only canonical comparison omits them.
        return {'case_id':case['id'],'passed':True,'actions':actions,'status':report.status,
            'correction':checks,'acl_checks_passed':True,'cache_no_new_draft':True,
            'independent_company_b_verified':independent_b,
            'context_fidelity':'CHECKED' if inputs else 'NOT_APPLICABLE',
            'canonical':canonical,'raw_report':report.model_dump(mode='json'),
            'prepared_input_sha256':quality.digest(inputs[0]) if inputs else None,
            'news_sha256':quality.digest(data['news']),
            'corpus_sha256':quality.digest(quality.source_corpus(case,data)),
            'context_sha256':quality.digest(inputs[0]['company_source_assertions']) if inputs else None}


def test_quality_twelve_scenarios_three_fresh_runs_and_isolation(identity_dsn,tmp_path):
    async def run():
        data=quality.fixtures()
        records=[]
        for case in data['scenarios']:
            runs=[await execute_case(identity_dsn,case,data) for _ in range(3)]
            assert runs[0]['canonical']==runs[1]['canonical']==runs[2]['canonical'],case['id']
            assert len({r['context_sha256'] for r in runs})==1
            assert len({r['news_sha256'] for r in runs})==1 and len({r['corpus_sha256'] for r in runs})==1
            records.append({'id':case['id'],'purpose':case['purpose'],'fresh_runs':3,
                'repeatable':True,'runs':runs})
        a,b,changed=[r['runs'][0] for r in records[:3]]
        assert a['news_sha256']==b['news_sha256']==changed['news_sha256']
        assert a['corpus_sha256']==b['corpus_sha256']==changed['corpus_sha256']
        assert len({a['context_sha256'],b['context_sha256'],changed['context_sha256']})==3
        # Identical intentionally empty drafts are NOT successful personalization.
        assert a['canonical']['analysis']['summary']==b['canonical']['analysis']['summary']
        report={'manifest':quality.manifest(),'cases':records,'claims':quality.claim_metrics(),
                'case_pass_count':len(records),'fresh_runs':36,'real_llm_calls':0,
                'personalization_completeness':'NOT_EVALUATED','recommendation_grounding':'NOT_EVALUATED',
                'context_fidelity':'CHECKED_FOR_FIXED_PROFILES',
                'limitations':['Fixed fake outputs do not evaluate a model.','Labels await independent expert review.',
                               'Semantic entailment is not proved.','Whole-item removal may remove a useful qualification.']}
        report['manifest']['git_head']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        write_json(tmp_path/'quality-report.json',report)
    asyncio.run(run())
