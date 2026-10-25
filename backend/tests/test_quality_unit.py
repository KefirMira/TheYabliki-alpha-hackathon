import copy
import json
import sys
import subprocess
from pathlib import Path
import pytest
from evaluation import quality
from schemas.preparation_diagnostics import PreparationDiagnostic
from services.preparation_diagnostics import safe_diagnostic
from types import SimpleNamespace


def test_fixed_labels_are_separate_from_predictions_and_expert_status_is_honest():
    data=quality.fixtures()
    assert len(data['scenarios'])==12 and len(data['claims'])==24
    assert all(c['reason'] and 'review' not in c and 'expected_codes' not in c for c in data['claims'])
    assert data['annotation']['independent_expert_review']=='PENDING'
    assert data['scenarios'][0]['summary']==data['scenarios'][1]['summary']
    assert data['scenarios'][0]['industry']!=data['scenarios'][1]['industry']


def test_metrics_are_reproducible_and_unknown_not_a_true_positive():
    a,b=quality.claim_metrics(),quality.claim_metrics()
    assert a==b
    confusion=a['confusion']
    assert sum(confusion.values())==20 and a['indeterminate_count']==4
    assert a['precision']==confusion['TP']/(confusion['TP']+confusion['FP'])
    assert a['recall']==confusion['TP']/12
    assert a['false_positive_rate']==confusion['FP']/8
    for row in a['records']:
        assert row['financial_truth']=='NOT_EVALUATED'
        assert row['review']['financial_correctness']=='UNKNOWN'
        if row['label']=='INDETERMINATE':assert row['benchmark_classification']=='EXCLUDED_INDETERMINATE'
        if row['benchmark_classification']=='TP':
            assert any(f['disposition']=='NEEDS_REVIEW' and f['code'] in quality.TARGETS[row['category']]
                       for f in row['review']['findings'])
    assert a['semantic_entailment']=='NOT_EVALUATED'


def test_manifest_has_no_invented_quality_score_and_tracks_sources():
    result=quality.manifest()
    assert result['personalization_completeness']==result['recommendation_grounding']=='NOT_EVALUATED'
    assert len(result['fixture_sha256'])==64 and result['real_llm_calls']==0
    assert all(len(value)==64 for value in result['source_sha256'].values())


def test_cli_cannot_enable_real_requests_or_accept_arbitrary_data(monkeypatch):
    monkeypatch.setattr(sys,'argv',['quality','--real'])
    with pytest.raises(SystemExit) as error:quality.main()
    assert error.value.code==2


def test_claim_cli_only_writes_local_synthetic_artifacts(tmp_path,monkeypatch):
    monkeypatch.setattr(quality,'OUTPUT',tmp_path)
    monkeypatch.setattr(sys,'argv',['quality'])
    quality.main()
    folder=next(tmp_path.iterdir())
    assert {p.name for p in folder.iterdir()}=={'claims.json','manifest.json'}
    assert json.loads((folder/'claims.json').read_text(encoding='utf-8'))==quality.claim_metrics()


def test_diagnostics_never_stringifies_exception_or_custom_class_name():
    class Hostile(Exception):
        def __str__(self):raise AssertionError('Must not stringify')
        def __repr__(self):raise AssertionError('Must not repr')
    error=Hostile('SYNTHETIC-SECRET-SENTINEL')
    result=safe_diagnostic('bad-stage-SYNTHETIC-SECRET-SENTINEL',error)
    assert result.stage==result.family=='UNKNOWN'
    assert 'SENTINEL' not in result.model_dump_json()
    assert result.retry_allowed is False
    with pytest.raises(ValueError):
        PreparationDiagnostic(stage='UNKNOWN',family='UNKNOWN',message='secret')


@pytest.mark.parametrize('fault',['citation','duplicate','tamper','metadata'])
def test_source_faults_are_detected_at_their_actual_boundary(fault,bundle_factory):
    from services.financial_review_service import review_financial_analysis
    from services.local_adaptive_service import LocalAdaptiveAgent, AgentStopped
    from services.synthetic_news_execution_service import LocalFakeAnalysisSDK
    from schemas.orchestration import OrchestrationTrace
    from schemas.persisted_analysis import PersistableAnalysis
    from services.company_context_service import build_context
    bundle=bundle_factory()
    context=build_context(dict(incoming_rows=0,incoming_counterparties=0,outgoing_rows=0,outgoing_counterparties=0))
    evidence=[e.model_dump() for e in bundle.evidence]
    if fault=='citation':
        bundle.analysis.summary='Условный вывод [Источник 999].'
        review=review_financial_analysis(bundle.analysis,context,evidence,'Synthetic')
        assert review.blocking and any(f.code=='CITATION_SOURCE_NOT_FOUND' for f in review.findings)
    elif fault=='duplicate':
        with pytest.raises(ValueError,match='DUPLICATE'):
            review_financial_analysis(bundle.analysis,context,evidence+evidence[:1],'Synthetic')
    elif fault=='tamper':
        corpus=[dict(source=e['document'],page=e['page'],chunk_id=e['chunk_id'],date=e['date'],text=e['text']) for e in evidence]
        evidence[0]['text']='Invented quotation'
        with pytest.raises(AgentStopped,match='PROVENANCE'):
            LocalAdaptiveAgent(LocalFakeAnalysisSDK(),OrchestrationTrace()).ensure_corpus(evidence,corpus)
    else:
        bundle.analysis.sources[0].page+=1
        with pytest.raises(ValueError):PersistableAnalysis.model_validate(bundle.model_dump())


def test_correction_checker_rejects_new_claim_and_keeps_company_identity(bundle_factory):
    from schemas.orchestration import OrchestrationTrace
    case=quality.fixtures()['scenarios'][0]
    bundle=bundle_factory()
    for key,value in quality.draft(case).items():setattr(bundle.analysis,key,value)
    bundle.analysis.risks=['Компания получит 999% прибыли.']
    report=SimpleNamespace(result=SimpleNamespace(analysis=bundle.analysis),
        orchestration=OrchestrationTrace(),status='COMPLETED',error_code=None,financial_review=None)
    assert quality.correction_checks(case,report)['no_new_claims'] is False
    assert quality.canonical_execution(report)['analysis']['company_id']=='SYNTH-COMPANY-A'


def test_claim_evaluator_import_does_not_load_settings_or_sdk():
    # Separate interpreter: conftest/main imports cannot conceal an accidental .env read.
    program="""
import sys, types, socket
def denied(*a, **k): raise AssertionError('dotenv forbidden')
sys.modules['dotenv']=types.SimpleNamespace(load_dotenv=denied)
sys.modules['openai']=None
socket.socket.connect=denied
from evaluation.quality import claim_metrics
assert 'settings' not in sys.modules
assert len(claim_metrics()['records'])==24
"""
    result=subprocess.run([sys.executable,'-B','-c',program],capture_output=True,text=True,
        cwd=Path(__file__).resolve().parents[1])
    assert result.returncode==0,result.stderr


@pytest.mark.parametrize('error,family',[(ValueError('SYNTHETIC-SECRET'),'VALUE'),
    (TypeError('SYNTHETIC-SECRET'),'TYPE'),(TimeoutError('SYNTHETIC-SECRET'),'CANCEL_OR_TIMEOUT')])
def test_diagnostic_categories_have_no_free_text(error,family):
    result=safe_diagnostic('rag_search',error)
    assert result.family==family and 'SYNTHETIC-SECRET' not in result.model_dump_json()
