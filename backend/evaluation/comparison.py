"""Offline-only paired comparison. No real flag, dotenv, SDK, database or file corpus."""
import argparse
import asyncio
import csv
from difflib import SequenceMatcher
import hashlib
import json

from pydantic import ConfigDict

from evaluation.inputs import synthetic_chunks
from evaluation.runner import OUTPUT_ROOT, fake_complete, make_plan, run, write_json
from evaluation.scenarios import scenarios
from schemas.company import CompanyProfile
from services.structured_analysis_service import parse_structured_analysis

CRITERIA = ['specific_company_features','risk_opportunity_differences','recommendation_grounding',
            'no_fabricated_financials','source_support','financial_caution']


class ComparisonProfile(CompanyProfile):
    """Evaluation fixture only; these fields do not extend the public backend API."""
    model_config=ConfigDict(extra='forbid')
    synthetic_fixture: bool = True
    loan_product_flag: bool
    deposit_product_flag: bool
    credit_terms: str = 'Неизвестны: признак продукта не доказывает наличие долга или его отсутствие.'
    business_features: list[str]
    missing_financial_fields: list[str] = ['выручка','долг','валюта','ставка по договору','период']


def comparison_cases():
    news=scenarios()[0]['news']
    profiles=[
        ('fuel','Оптовая торговля топливом',True,False,
         ['Закупает товарные запасы до оплаты поставок покупателями.',
          'Покупатели — транспортные предприятия; расчёт после отгрузки.'],
         'Обсудить условное финансирование запасов и спрос транспортных покупателей; не утверждать наличие долга.'),
        ('software','Разработка программного обеспечения',False,True,
         ['Основные затраты — персонал проектной команды.',
          'Заказчики оплачивают проекты после приёмки этапов.'],
         'Учитывать оплату этапов и затраты на персонал; отсутствие признака кредитного продукта не доказывает отсутствие долгов.'),
    ]
    return [{'id':'comparison-rate-'+key,'category':'synthetic-paired-comparison','news':news,
        'company':ComparisonProfile(company_id='SYNTH-COMPARE-'+key,industry=industry,
            loan_product_flag=loan,deposit_product_flag=deposit,business_features=features).model_dump(),
        'review_expectation':expectation}
        for key,industry,loan,deposit,features,expectation in profiles]


def comparison_plan():
    cases=comparison_cases()
    limits=dict(max_requests=2,max_input_tokens=8000,max_output_tokens=1000,
        request_seconds=60,total_seconds=120,billing_mode='organizer_rub_quota',
        input_rate=None,output_rate=None,budget_usd=None)
    prepared,plan=make_plan(cases,synthetic_chunks(),limits,profile_model=ComparisonProfile)
    assert prepared[0][0]['news']==prepared[1][0]['news']
    assert prepared[0][1]['evidence']==prepared[1][1]['evidence']
    plan.update(execution_available='FAKE_ONLY',real_comparison_requires_separate_permission=True,
        expected_total_input_planning_bound=sum(p['input_token_planning_bound'] for _,p in prepared),
        total_output_token_limit=2000,
        note='Two sequential future calls, one per profile; no retries or fallback. Existing single organizer-gateway mode is unchanged and cannot execute this pair.')
    return prepared,plan


def compare_records(records):
    report={'mode':'fake','human_review_required':True,'quality_score':None,
            'criteria':{name:'NOT_ASSESSED' for name in CRITERIA},'profiles':{},'pair':{}}
    parsed=[]
    for record in records:
        key=record['scenario']['id']
        raw=(record.get('response') or {}).get('raw','')
        try:
            content=parse_structured_analysis(raw).model_dump()
        except ValueError:
            report['profiles'][key]={'schema_valid':False,'review_required':True}
            parsed.append(None)
            continue
        text=' '.join([content['summary'],*content['risks'],*content['opportunities'],*content['recommendations']]).casefold()
        markers={'comparison-rate-fuel':['топлив','запас','отгруз','транспорт'],
                 'comparison-rate-software':['персонал','проект','этап','программ']}
        report['profiles'][key]={'schema_valid':True,'lexical_feature_mentions':
            [word for word in markers[key] if word in text],
            'technical_checks':record['checks'],
            'note':'Mentions and different wording do not prove personalization or correctness.'}
        parsed.append(content)
    if len(parsed)==2 and all(parsed):
        for field in ['summary','risks','opportunities','recommendations']:
            a,b=[json.dumps(p[field],ensure_ascii=False,sort_keys=True) for p in parsed]
            report['pair'][field]={'identical':a==b,'lexical_similarity':round(SequenceMatcher(None,a,b).ratio(),4)}
        report['pair']['warning']='Fake answers test the harness, never model quality.'
    return report


async def execute(args, *, complete=fake_complete, root=OUTPUT_ROOT):
    prepared,plan=comparison_plan()
    print(json.dumps({'mode':'comparison-plan-no-llm','plan':plan},ensure_ascii=False))
    if args.plan:return 0
    folder=await run(prepared,plan,complete,real=False,root=root,
        metadata={'synthetic_rag':True,'corpus_files':[],'comparison':True,'requested_model':'fake-no-llm'})
    records=[json.loads((folder/(case['id']+'.json')).read_text(encoding='utf-8')) for case,_ in prepared]
    report=compare_records(records)
    report['news_sha256']=hashlib.sha256(prepared[0][0]['news'].encode()).hexdigest()
    report['shared_evidence_sha256']=hashlib.sha256(json.dumps(prepared[0][1]['evidence'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    write_json(folder/'comparison.json',report)
    with (folder/'comparison-review.tsv').open('x',encoding='utf-8',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=['scenario_id','mode',*CRITERIA,'reviewer','notes'],delimiter='\t')
        writer.writeheader()
        for case,_ in prepared:writer.writerow({'scenario_id':case['id'],'mode':'fake'})
    (folder/'comparison-review.tsv').chmod(0o600)
    print(json.dumps({'results':str(folder),'mode':'fake','human_review_required':True},ensure_ascii=False))
    return 0 if all(r['status']=='RECEIVED' for r in records) else 1


def main(argv=None):
    parser=argparse.ArgumentParser(description='Synthetic paired comparison: fake SDK or plan only; no real execution')
    parser.add_argument('--plan',action='store_true')
    args=parser.parse_args(argv)
    return asyncio.run(execute(args))


if __name__=='__main__':raise SystemExit(main())
