"""Fixed synthetic comparison; fake by default, real organizer pair requires explicit flags."""
import argparse
import asyncio
import csv
from difflib import SequenceMatcher
import hashlib
import json

from pydantic import ConfigDict

from evaluation.inputs import synthetic_chunks
from evaluation.runner import OUTPUT_ROOT, fake_complete, make_plan, run, write_json, sanitized, validate_real_plan
from evaluation.__main__ import configuration, real_client, complete_with_client
from evaluation.scenarios import scenarios
from evaluation.compact import VARIANT as COMPACT_VARIANT, RULES as COMPACT_RULES
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


def comparison_plan(args=None):
    cases=comparison_cases()
    variant=COMPACT_VARIANT if getattr(args,'compact',False) else 'comparison-baseline-v1'
    suffix=COMPACT_RULES if variant==COMPACT_VARIANT else ''
    if suffix:cases=[{**case,'evaluation_prompt_variant':variant} for case in cases]
    limits=dict(max_requests=getattr(args,'max_requests',2),max_input_tokens=getattr(args,'max_input_tokens',8000),
        max_output_tokens=getattr(args,'max_output_tokens',1000),
        request_seconds=getattr(args,'request_seconds',60),total_seconds=getattr(args,'total_seconds',120),
        billing_mode='organizer_comparison_rub_quota',
        input_rate=None,output_rate=None,budget_usd=None)
    prepared,plan=make_plan(cases,synthetic_chunks(),limits,profile_model=ComparisonProfile,question_suffix=suffix)
    validate_real_plan(plan)
    plan.update(execution_available='EXPLICIT_ORGANIZER_PAIR_ONLY',real_comparison_requires_separate_permission=True,
        prompt_variant=variant,question_suffix_sha256=hashlib.sha256(suffix.encode()).hexdigest(),
        expected_total_input_planning_bound=sum(p['input_token_planning_bound'] for _,p in prepared),
        total_output_token_limit=2*limits['max_output_tokens'],
        note='Two sequential calls, one per fixed synthetic profile; no retries or fallback. Existing single organizer-gateway mode is unchanged.')
    return prepared,plan


def validate_fixed_pair(prepared, plan):
    variant=plan['prompt_variant']
    if variant not in {'comparison-baseline-v1',COMPACT_VARIANT}:raise ValueError('COMPARISON_FIXTURE_MISMATCH')
    suffix=COMPACT_RULES if variant==COMPACT_VARIANT else ''
    cases=comparison_cases()
    if suffix:cases=[{**case,'evaluation_prompt_variant':variant} for case in cases]
    expected,_=make_plan(cases,synthetic_chunks(),plan['limits'],profile_model=ComparisonProfile,question_suffix=suffix)
    if plan['question_suffix_sha256']!=hashlib.sha256(suffix.encode()).hexdigest():raise ValueError('COMPARISON_FIXTURE_MISMATCH')
    if prepared != expected or prepared[0][0]['news'] != prepared[1][0]['news'] or prepared[0][1]['evidence'] != prepared[1][1]['evidence']:
        raise ValueError('COMPARISON_FIXTURE_MISMATCH')


def compare_records(records):
    report={'mode':records[0]['mode'],'human_review_required':True,'quality_score':None,
            'criteria':{name:'NOT_ASSESSED' for name in CRITERIA},'profiles':{},'pair':{}}
    parsed=[]
    for record in records:
        key=record['scenario']['id']
        raw=(record.get('response') or {}).get('raw','')
        try:
            content=parse_structured_analysis(raw).model_dump()
        except ValueError:
            report['profiles'][key]={'schema_valid':False,'review_required':True,'status':record['status'],
                                     'usage':(record.get('response') or {}).get('usage'),
                                     'technical_checks':record.get('checks')}
            parsed.append(None)
            continue
        text=' '.join([content['summary'],*content['risks'],*content['opportunities'],*content['recommendations']]).casefold()
        markers={'comparison-rate-fuel':['топлив','запас','отгруз','транспорт'],
                 'comparison-rate-software':['персонал','проект','этап','программ']}
        report['profiles'][key]={'schema_valid':True,'lexical_feature_mentions':
            [word for word in markers[key] if word in text],
            'technical_checks':record['checks'],'status':record['status'],
            'usage':record['response'].get('usage'),'elapsed_seconds':record['elapsed_seconds'],
            'note':'Mentions and different wording do not prove personalization or correctness.'}
        parsed.append(content)
    if len(parsed)==2 and all(parsed):
        for field in ['summary','risks','opportunities','recommendations']:
            a,b=[json.dumps(p[field],ensure_ascii=False,sort_keys=True) for p in parsed]
            report['pair'][field]={'identical':a==b,'lexical_similarity':round(SequenceMatcher(None,a,b).ratio(),4)}
        report['pair']['warning']=('Fake answers test the harness, never model quality.' if report['mode']=='fake'
                                  else 'One answer per profile is a pilot, not statistical evidence or factual verification.')
    return report


async def execute(args, *, complete=fake_complete, root=OUTPUT_ROOT):
    prepared,plan=comparison_plan(args)
    validate_fixed_pair(prepared,plan)
    real=getattr(args,'real',False)
    config=configuration(args) if real else {}
    secret=config.get('LLM_API_KEY','') if real else ''
    print(json.dumps({'mode':'comparison-plan-no-llm' if args.plan else 'real' if real else 'fake','plan':plan},ensure_ascii=False))
    if args.plan:return 0
    metadata={'synthetic_rag':True,'corpus_files':[],'comparison':True,
              'prompt_variant':plan['prompt_variant'],
              'requested_model':config.get('LLM_MODEL') if real else 'fake-no-llm',
              'provider_host':getattr(args,'allow_provider_host',None) if real else None,
              'unknown_cost_acknowledged':getattr(args,'acknowledge_unknown_cost',False)}
    if real:
        client=real_client(config)
        async def sdk_complete(messages,*,max_tokens,timeout):
            return await complete_with_client(client,config,messages,max_tokens=max_tokens,timeout=timeout)
        try:
            folder=await run(prepared,plan,sdk_complete,real=True,secret=secret,root=root,metadata=metadata)
        finally:await client.close()
    else:
        folder=await run(prepared,plan,complete,real=False,root=root,metadata=metadata)
    records=[json.loads((folder/(case['id']+'.json')).read_text(encoding='utf-8')) for case,_ in prepared]
    report=compare_records(records)
    report['news_sha256']=hashlib.sha256(prepared[0][0]['news'].encode()).hexdigest()
    report['shared_evidence_sha256']=hashlib.sha256(json.dumps(prepared[0][1]['evidence'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    write_json(folder/'comparison.json',report,secret)
    with (folder/'comparison-review.tsv').open('x',encoding='utf-8',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=['scenario_id','mode',*CRITERIA,'reviewer','notes'],delimiter='\t')
        writer.writeheader()
        for case,_ in prepared:writer.writerow({'scenario_id':case['id'],'mode':report['mode']})
    (folder/'comparison-review.tsv').chmod(0o600)
    # Side-by-side inputs/results without headers or secrets; escape spreadsheet formulas.
    with (folder/'comparison-responses.tsv').open('x',encoding='utf-8',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=['scenario_id','mode','status','industry','loan_product_flag',
            'deposit_product_flag','summary','risks','opportunities','recommendations','usage','elapsed_seconds','warnings'],delimiter='\t')
        writer.writeheader()
        for record in records:
            try:content=parse_structured_analysis((record.get('response') or {}).get('raw','')).model_dump()
            except ValueError:content={}
            company=record['scenario']['company']
            row=dict(scenario_id=record['scenario']['id'],mode=record['mode'],status=record['status'],
                **{k:company[k] for k in ('industry','loan_product_flag','deposit_product_flag')},
                **{k:content.get(k) for k in ('summary','risks','opportunities','recommendations')},
                usage=(record.get('response') or {}).get('usage'),elapsed_seconds=record['elapsed_seconds'],warnings=record.get('checks'))
            row={k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else '' if v is None else str(v) for k,v in sanitized(row,secret).items()}
            writer.writerow({k:"'"+v if v.lstrip().startswith(('=','+','-','@')) else v for k,v in row.items()})
    (folder/'comparison-responses.tsv').chmod(0o600)
    summary=json.loads((folder/'summary.json').read_text(encoding='utf-8'))
    print(json.dumps({'results':str(folder),'mode':report['mode'],'human_review_required':True,
                      'error_codes':summary['error_codes']},ensure_ascii=False))
    return 0 if not summary['stopped'] and all(r['status']=='RECEIVED' for r in records) else 1


def arguments(argv=None):
    parser=argparse.ArgumentParser(description='Fixed synthetic comparison: fake by default, explicit organizer pair')
    parser.add_argument('--plan',action='store_true')
    parser.add_argument('--compact',action='store_true',help='Opt-in compact evaluation prompt; production and baseline remain unchanged')
    parser.add_argument('--real',action='store_true')
    parser.add_argument('--organizer-gateway',action='store_true')
    parser.add_argument('--synthetic-rag',action='store_true')
    parser.add_argument('--allow-provider-host')
    parser.add_argument('--allow-rag-transfer',action='store_true')
    parser.add_argument('--acknowledge-unknown-cost',action='store_true')
    parser.add_argument('--max-requests',type=int,choices=[2],default=2)
    parser.add_argument('--max-input-tokens',type=int,default=8000)
    parser.add_argument('--max-output-tokens',type=int,default=1000)
    parser.add_argument('--request-seconds',type=float,default=60)
    parser.add_argument('--total-seconds',type=float,default=120)
    args=parser.parse_args(argv)
    if not (1<=args.max_input_tokens<=8000 and 1<=args.max_output_tokens<=1000
            and 1<=args.request_seconds<=60 and 1<=args.total_seconds<=120):
        parser.error('Comparison limits outside safe range')
    if args.real and (not args.organizer_gateway or not args.synthetic_rag or not args.allow_provider_host
                     or (not args.plan and (not args.allow_rag_transfer or not args.acknowledge_unknown_cost))):
        parser.error('Real pair requires organizer gateway, synthetic RAG, allowed host and explicit transfer/unknown cost acknowledgements')
    if not args.real and (args.organizer_gateway or args.allow_provider_host or args.allow_rag_transfer or args.acknowledge_unknown_cost):
        parser.error('Real acknowledgements require --real')
    return args


def main(argv=None):
    args=arguments(argv)
    try:return asyncio.run(execute(args))
    except KeyboardInterrupt:
        print('INTERRUPTED: inspect intent files; do not retry automatically.')
        return 130
    except Exception:
        print(json.dumps({'error':'COMPARISON_ERROR_DETAILS_WITHHELD','do_not_auto_retry':True}))
        return 1


if __name__=='__main__':raise SystemExit(main())
