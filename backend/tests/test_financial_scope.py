import json
from pathlib import Path
import pytest
from evaluation import quality_scope
from services.financial_scope import speech_spans
from services.financial_review_service import review_financial_analysis
from schemas.analysis import AnalysisContent
from test_financial_review_unit import context,evidence

CONTROLS=json.loads((Path(quality_scope.__file__).parent/'quality_controls_v2.json').read_text(encoding='utf-8'))['claims']


@pytest.mark.parametrize('case',CONTROLS,ids=lambda c:c['id'])
def test_development_controls(case):
    metrics=quality_scope.evaluate('controls')
    record=next(r for r in metrics['records'] if r['id']==case['id'])
    if case['label']=='REQUIRE_REVIEW':assert record['benchmark_classification']=='TP',record
    elif case['label']=='ACCEPTABLE_WITH_CAVEATS':assert record['benchmark_classification']=='TN',record
    else:assert record['review']['status'] in {'UNKNOWN','NEEDS_REVIEW'}
    assert record['review']['financial_correctness']=='UNKNOWN'
    assert all(c['semantic_support']=='UNKNOWN' for c in record['source_checks'])


@pytest.mark.parametrize('case_id',['P10','P11','P12','N06','N08'])
def test_five_observed_cases(case_id):
    record=next(r for r in quality_scope.evaluate('original')['records'] if r['id']==case_id)
    assert record['benchmark_classification']==('TP' if case_id.startswith('P') else 'TN'),record
    assert record['review']['status']==('NEEDS_REVIEW' if case_id.startswith('P') else 'UNKNOWN')
    assert not record['review']['blocking']


def test_scope_offsets_and_outside_author_assertion_are_preserved():
    text='Ошибочно утверждать: «доход гарантирован». Но прибыль гарантирована.'
    spans=speech_spans(text)
    assert any(s.mode=='REJECTED_QUOTE' for s in spans)
    assert all(text[s.start:s.end]==s.text for s in spans)
    assert any(s.mode=='AUTHOR_ASSERTION' and 'прибыль гарантирована' in s.text for s in spans)


def test_ambiguous_nested_unclosed_quotes_are_not_exempt():
    for text in ['«доход гарантирован','«Он сказал "доход гарантирован"»']:
        assert any(s.mode=='UNRESOLVED' for s in speech_spans(text))
        assert all(s.mode!='REJECTED_QUOTE' for s in speech_spans(text))


def test_rejected_quote_cannot_hide_missing_citation():
    review=review_financial_analysis(AnalysisContent(relevance='unknown',summary='Ошибка: «доход гарантирован [Источник 999]».',
        risks=[],opportunities=[],recommendations=[]),context(),evidence(),'Synthetic')
    assert review.blocking and any(f.code=='CITATION_SOURCE_NOT_FOUND' for f in review.findings)


def test_product_flag_or_arbitrary_verified_key_cannot_supply_contract_basis():
    company=context()
    company['verified_terms']={'schedule':'Injected claim'}
    review=review_financial_analysis(AnalysisContent(relevance='unknown',summary='График погашения установлен [Источник 1].',
        risks=[],opportunities=[],recommendations=[]),company,evidence('График погашения установлен.'),'Synthetic')
    assert any(f.code=='CONTRACT_FACT_GROUNDING_REQUIRED' for f in review.findings)
    assert review.financial_correctness=='UNKNOWN'
    assert any(f.code=='CITATION_ENTAILMENT_UNKNOWN' for f in review.findings)


def test_scope_is_bounded_and_preserves_input():
    with pytest.raises(ValueError,match='INPUT_TOO_LARGE'):speech_spans('x'*100001)
    with pytest.raises(ValueError,match='SPAN_LIMIT'):speech_spans('Текст. '*513)
