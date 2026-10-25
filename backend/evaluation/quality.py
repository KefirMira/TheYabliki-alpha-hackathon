"""Fixed synthetic benchmark. No SDK, config, .env, database or real mode imports."""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import platform
import re
from uuid import uuid4

from evaluation.runner import write_json
from schemas.analysis import AnalysisContent
from services.company_context_service import build_context
from services.financial_review_service import review_financial_analysis

FIXTURE_PATH = Path(__file__).with_name('quality_fixtures.json')
OUTPUT = Path(__file__).resolve().parents[1]/'evaluation-results'
# Targeted signals are mapped independently of gold labels. Generic UNKNOWN is not a detection.
TARGETS = {
    'borrowing_cost': {'UNSUPPORTED_UNCHANGED_BORROWING_COST'},
    'contract': {'COMPANY_CONTRACT_NUMBER_UNVERIFIED','FINANCIAL_NUMBER_NOT_IN_INPUT'},
    'company_fact': {'COMPANY_FACT_NOT_ESTABLISHED'},
    'counts': {'STRUCTURAL_COUNT_AS_FINANCIAL_INFERENCE'},
    'recommendation': {'COMPANY_PROJECTION_AS_FACT'},
    'source_support': {'CITED_SOURCE_NUMBER_NOT_FOUND'},
}


def digest(value):
    # Same canonical representation as preparation, without importing its settings loader.
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
        default=str,allow_nan=False).encode('utf-8')).hexdigest()


def fixtures():
    data = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))
    if ([c['id'] for c in data['scenarios']] != [f'Q{i:02}' for i in range(1,13)]
            or len({c['id'] for c in data['claims']}) != 24
            or Counter(c['label'] for c in data['claims']) != {
                'REQUIRE_REVIEW':12,'ACCEPTABLE_WITH_CAVEATS':8,'INDETERMINATE':4}):
        raise ValueError('INVALID_FIXED_QUALITY_FIXTURES')
    return data


def source_corpus(case, data):
    selected = {'baseline':data['corpus'][:2], 'single':data['corpus'][:1],
                'gold':data['corpus'][3:], 'empty':[]}[case['corpus']]
    return copy.deepcopy(selected)


def draft(case):
    return dict(relevance='unknown',summary=case['summary'],risks=case['risks'],
                opportunities=[],recommendations=[])


def claim_metrics(*, claims=None, targets=None):
    data = fixtures()
    selected_claims=data['claims'] if claims is None else claims
    selected_targets=TARGETS if targets is None else targets
    context = build_context(dict(industry='Синтетическая отрасль',incoming_rows=3,
        incoming_counterparties=2,outgoing_rows=1,outgoing_counterparties=1))
    evidence = [dict(id=1,document=data['corpus'][0]['source'],page=1,chunk_id=1,
        date=data['corpus'][0]['date'],score=0.5,text=data['corpus'][0]['text'])]
    records=[]
    for case in selected_claims:
        analysis=AnalysisContent(relevance='unknown',summary=case['text'],risks=[],opportunities=[],recommendations=[])
        review=review_financial_analysis(analysis,context,evidence,data['news'])
        targeted={f.code for f in review.findings if f.disposition=='NEEDS_REVIEW' and f.field=='summary'}
        positive=bool(targeted & selected_targets[case['category']]) if case['label']=='REQUIRE_REVIEW' else bool(targeted)
        classification = ('TP' if positive else 'FN') if case['label']=='REQUIRE_REVIEW' else (
            'FP' if positive else 'TN') if case['label']=='ACCEPTABLE_WITH_CAVEATS' else 'EXCLUDED_INDETERMINATE'
        records.append({**case,'review':review.model_dump(mode='json'),
            'prediction':'TARGETED_REVIEW_SIGNAL' if positive else 'NO_TARGETED_REVIEW_SIGNAL',
            'benchmark_classification':classification,
            'source_checks':[{'source_id':int(value),'present':int(value)==1,'semantic_support':'UNKNOWN'}
                for value in re.findall(r'\[Источник\s+(\d+)\]',case['text'],flags=re.I)],
            'financial_truth':'NOT_EVALUATED'})
    counts=Counter(r['benchmark_classification'] for r in records)
    tp,fp,fn,tn=[counts[k] for k in ('TP','FP','FN','TN')]
    return {'annotation':data['annotation'],'records':records,'confusion':dict(TP=tp,FP=fp,FN=fn,TN=tn),
        'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,
        'false_positive_rate':fp/(fp+tn) if fp+tn else None,
        'false_positives':[r['id'] for r in records if r['benchmark_classification']=='FP'],
        'false_negatives':[r['id'] for r in records if r['benchmark_classification']=='FN'],
        'review_status_counts':dict(Counter(r['review']['status'] for r in records)),
        'finding_disposition_counts':dict(Counter(f['disposition'] for r in records for f in r['review']['findings'])),
        'indeterminate_count':sum(r['label']=='INDETERMINATE' for r in records),'semantic_entailment':'NOT_EVALUATED',
        'interpretation':'Metrics evaluate review signalling, never financial truth; UNKNOWN is not a true positive.'}


def canonical_execution(report):
    """Drop only technical trace/DB IDs; preserve company identity, evidence and decisions."""
    trace=report.orchestration.model_dump(mode='json') if report.orchestration else None
    if trace:
        # PREPARE news snapshot includes technical timestamps; subsequent result hashes may
        # incorporate technical IDs. Hashes remain in raw trace, not the canonical comparison.
        for event in trace['events']:
            event.pop('before_sha256',None)
            event.pop('after_sha256',None)
    return {'status':report.status,'error_code':report.error_code,
        'analysis':report.result.analysis.model_dump(mode='json') if report.result else None,
        'review':report.financial_review.model_dump(mode='json') if report.financial_review else None,
        'trace':trace}


def correction_checks(case, report):
    if report.result is None:
        return {'status':'NOT_APPLICABLE','no_new_claims':None}
    before=draft(case)
    after={key:getattr(report.result.analysis,key) for key in before}
    expected=copy.deepcopy(before)
    removals=[e for e in report.orchestration.events if e.tool=='REMOVE_CLAIM']
    if removals:
        key,index=re.fullmatch(r'(risks|opportunities|recommendations)\[(\d+)\]',removals[0].field).groups()
        del expected[key][int(index)]
    return {'status':'CHECKED','no_new_claims':after==expected,
            'removed_items':len(removals),'all_other_fields_unchanged':after==expected,
            'collateral_qualification_removed':case['id']=='Q12' and bool(removals),
            'semantic_quality':'NOT_EVALUATED'}


def manifest():
    from importlib.metadata import version
    return {'benchmark_version':'local-quality-v1','fixture_sha256':digest(fixtures()),
        'source_sha256':{name:digest((Path(__file__).resolve().parents[1]/name).read_text(encoding='utf-8'))
            for name in ['services/local_adaptive_service.py','services/financial_review_service.py',
                         'services/analysis_preparation_service.py','services/financial_assertion_rules.py',
                         'services/company_context_service.py','services/search_service.py',
                         'services/synthetic_news_execution_service.py','services/financial_scope.py','evaluation/quality.py']},
        'python':platform.python_version(),'dependencies':{p:version(p) for p in ['pydantic','SQLAlchemy','scikit-learn']},
        'scope':'synthetic-fake-only','real_llm_calls':0,
        'personalization_completeness':'NOT_EVALUATED','recommendation_grounding':'NOT_EVALUATED'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.parse_args()  # No real flag, input file, network, DSN or configurable corpus.
    folder=OUTPUT/('quality-'+uuid4().hex)
    folder.mkdir(parents=True,exist_ok=False,mode=0o700)
    write_json(folder/'claims.json',claim_metrics())
    write_json(folder/'manifest.json',manifest())
    print(json.dumps({'output':str(folder),'scope':'24 synthetic claims only',
        'scenarios':'Run test_auth_quality_integration.py for 12 PostgreSQL scenarios',
        'real_llm_calls':0}))


if __name__=='__main__':
    main()
