"""Local rules evaluation; operational risk signals are not semantic entailment."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from evaluation import quality
from evaluation.runner import write_json
from services.financial_scope import speech_spans

ROOT=Path(__file__).parent
OPERATIONAL_TARGETS=copy.deepcopy(quality.TARGETS)
OPERATIONAL_TARGETS['recommendation'].add('UNCONDITIONAL_FINANCIAL_OUTCOME')
OPERATIONAL_TARGETS['source_support'].add('CONTRACT_FACT_GROUNDING_REQUIRED')
RULE_FILES=('services/financial_scope.py','services/financial_review_service.py',
            'services/financial_assertion_rules.py','services/local_adaptive_service.py',
            'evaluation/quality.py','evaluation/quality_scope.py')


def rules_hashes():
    return {name:hashlib.sha256((ROOT.parent/name).read_bytes()).hexdigest() for name in RULE_FILES}


def evaluate(name):
    if name=='original':
        data=quality.fixtures()
    elif name in {'controls','holdout'}:
        data=json.loads((ROOT/f'quality_{name}_v2.json').read_text(encoding='utf-8'))
    else:raise ValueError('UNKNOWN_FIXED_SUITE')
    if name=='holdout':
        freeze=json.loads((ROOT/'quality_scope_freeze.json').read_text(encoding='utf-8'))
        if rules_hashes()!=freeze['rules_sha256']:
            raise ValueError('RULES_CHANGED_AFTER_HOLDOUT_FREEZE')
        if hashlib.sha256((ROOT/'quality_holdout_v2.json').read_bytes()).hexdigest()!=freeze['holdout_sha256']:
            raise ValueError('HOLDOUT_CHANGED')
    result=quality.claim_metrics(claims=data['claims'],targets=OPERATIONAL_TARGETS)
    result['metric_version']='review-actionability-v2'
    result['annotation']=data['annotation']
    result['suite']=name
    result['rules_sha256']=rules_hashes()
    for record in result['records']:
        record['scopes']=[{'start':s.start,'end':s.end,'mode':s.mode} for s in speech_spans(record['text'])]
    if name=='original':
        legacy=quality.claim_metrics()
        result['legacy_target_map_v1']={key:legacy[key] for key in ['confusion','precision','recall','false_positive_rate']}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--holdout',action='store_true',help='Evaluate frozen holdout; never tune rules afterwards')
    args=parser.parse_args()
    report={'manifest':quality.manifest(),'original':evaluate('original'),'controls':evaluate('controls'),
        'semantic_support':'UNKNOWN','personalization':'NOT_EVALUATED','real_llm_calls':0}
    if args.holdout:report['holdout']=evaluate('holdout')
    folder=quality.OUTPUT/('scope-'+uuid4().hex)
    folder.mkdir(parents=True,mode=0o700)
    write_json(folder/'scope-report.json',report)
    print(json.dumps({'results':str(folder),'real_llm_calls':0,
        'suites':{key:{k:report[key][k] for k in ['confusion','precision','recall','false_positives','false_negatives']}
            for key in ['original','controls','holdout'] if key in report}},ensure_ascii=False))


if __name__=='__main__':main()
