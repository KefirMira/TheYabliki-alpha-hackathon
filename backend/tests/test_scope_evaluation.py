import hashlib
import json
from pathlib import Path
import pytest
from evaluation import quality,quality_scope


def test_frozen_holdout_is_unchanged_and_metrics_are_reproducible():
    first=quality_scope.evaluate('holdout')
    assert first==quality_scope.evaluate('holdout')
    assert len(first['records'])==16 and first['indeterminate_count']==2
    assert sum(first['confusion'].values())==14
    assert first['semantic_entailment']=='NOT_EVALUATED'
    assert all(c['semantic_support']=='UNKNOWN' for r in first['records'] for c in r['source_checks'])
    assert hashlib.sha256((Path(quality_scope.__file__).parent/'quality_holdout_v2.json').read_bytes()).hexdigest()==(
        '78a24edea11af04ce24a8b28b5742a213746561304753c74c579730a0a566dee')


def test_legacy_and_operational_metrics_are_not_silently_substituted():
    result=quality_scope.evaluate('original')
    assert result['metric_version']=='review-actionability-v2'
    assert quality.TARGETS['recommendation']=={'COMPANY_PROJECTION_AS_FACT'}
    assert quality.TARGETS['source_support']=={'CITED_SOURCE_NUMBER_NOT_FOUND'}
    assert result['legacy_target_map_v1']['confusion']!=result['confusion']
    assert result['semantic_entailment']=='NOT_EVALUATED'


def test_holdout_rejects_rule_drift(monkeypatch):
    monkeypatch.setattr(quality_scope,'rules_hashes',lambda:{'changed':'hash'})
    with pytest.raises(ValueError,match='RULES_CHANGED'):quality_scope.evaluate('holdout')


def test_post_freeze_stress_measurement_records_unfixed_limitations(tmp_path):
    # Deliberate adversarial audit AFTER freeze, not inputs used to tune the rules.
    # Failure labels are measurements of review signalling, not failed runtime assertions.
    cases=[
        dict(id='S01',label='REQUIRE_REVIEW',category='recommendation',
             text='Доход не гарантирован, прибыль гарантирована.',reason='Negation must not cover a separate positive promise.'),
        dict(id='S02',label='ACCEPTABLE_WITH_CAVEATS',category='boundary',
             text='Факт и гипотеза разграничены: доход не гарантирован.',reason='Meta distinction followed by a cautious negative statement.')]
    result=quality.claim_metrics(claims=cases,targets=quality_scope.OPERATIONAL_TARGETS)
    assert len(result['records'])==2
    assert all(r['review']['financial_correctness']=='UNKNOWN' for r in result['records'])
    (tmp_path/'post-freeze-stress.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
