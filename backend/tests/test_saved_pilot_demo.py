"""Only pinned synthetic fixtures. No SDK/client/network."""
import copy
import json
from unittest.mock import patch

import pytest
from saved_pilot_demo import approved, ARTIFACT, ARTIFACT_SHA256, main
from services.synthetic_gateway_input import canonical, fixture


def test_actual_saved_content_sources_review_and_trace():
    data, bundle = approved()
    assert json.loads(data['content']) == {k: bundle.analysis.model_dump()[k]
        for k in ['relevance', 'summary', 'risks', 'opportunities', 'recommendations']}
    assert [f.text for f in bundle.evidence] == [c['text'] for c in fixture()['corpus']]
    assert [f.document for f in bundle.evidence] == ['synthetic-gateway-rate.txt', 'synthetic-gateway-production.txt']
    assert bundle.analysis.validation.passed is False
    assert sum(f.disposition == 'UNKNOWN' for f in bundle.financial_review.findings) == 16
    assert sum(f.disposition == 'NEEDS_REVIEW' for f in bundle.financial_review.findings) == 4
    assert bundle.orchestration.sdk_requests == 1  # historical, not a new call
    assert data['metadata']['service_seconds'] == pytest.approx(15.688, abs=.001)
    assert bundle.financial_review.financial_correctness == 'UNKNOWN'


@pytest.mark.parametrize('change', ['content', 'review', 'trace', 'secret', 'source'])
def test_changed_artifact_rejected_before_database(tmp_path, change):
    data = json.loads(ARTIFACT.read_text(encoding='utf-8'))
    if change == 'content':
        data['content'] = '{"summary":"forged"}'
    elif change == 'review':
        data['financial_review']['findings'] = []
    elif change == 'trace':
        data['orchestration']['paid_calls'] = 0
    elif change == 'source':
        data['sources'][0]['document'] = 'invented-bank.pdf'
    else:
        data['api_key'] = 'synthetic-secret'
    path = tmp_path / 'modified.json'
    path.write_text(canonical(data), encoding='utf-8')
    with patch('saved_pilot_demo.ARTIFACT', path), pytest.raises(ValueError, match='ARTIFACT_CHANGED'):
        approved()


def test_cli_apply_requires_confirmation_and_redacts(capsys, monkeypatch):
    monkeypatch.setenv('SAVED_PILOT_DATABASE_URL', 'synthetic-secret-dsn')
    assert main(['--expected-database','test_pilot','--apply']) == 1
    assert capsys.readouterr().out == '{"code": "SAVED_PILOT_IMPORT_FAILED_VERIFY_TARGET_AND_ARTIFACT"}\n'

def test_docker_packages_only_explicit_pilot_fixture():
    root = ARTIFACT.parents[1]
    docker = (root/'Dockerfile').read_text(encoding='utf-8')
    allowed = (root/'.dockerignore').read_text(encoding='utf-8')
    for name in ['saved_pilot_demo.py','fixtures/saved_llm_pilot_v1.json']:
        assert 'COPY '+name in docker
        assert '!'+name in allowed
    assert '!data/' not in allowed
    assert '!fixtures/*' not in allowed
