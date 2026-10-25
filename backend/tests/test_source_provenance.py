from copy import deepcopy
import pytest
from services.source_provenance import card_provenance, source_metadata
from integration_demo import seed


@pytest.mark.parametrize('document,format', [('example.txt', 'TXT'), ('REPORT.PDF', 'PDF'), ('opaque', 'UNKNOWN'), (None, 'UNKNOWN')])
def test_filename_is_not_publisher_or_verified_format(document, format):
    assert source_metadata(document) == {'declared_format': format, 'format_verified': False,
                                         'publisher': None, 'attribution_status': 'UNKNOWN'}


def test_legacy_txt_pdf_is_read_projection_only_preserving_provenance():
    sources = [{'id': 7, 'document': 'invented.txt', 'page': 2, 'chunk_id': 4, 'synthetic': True, 'date': '2026-01'}]
    evidence = [{'evidence_type': 'PDF', 'document': 'invented.txt', 'text': 'Exact source text', 'page': 2, 'chunk_id': 4}]
    before = deepcopy((sources, evidence))
    projected, rows = card_provenance(sources, evidence)
    assert (sources, evidence) == before
    assert rows[0] == {**evidence[0], 'evidence_type': 'DOCUMENT'}
    assert {k: v for k, v in projected[0].items() if k != 'provenance'} == sources[0]
    assert projected[0]['provenance']['publisher'] is None


@pytest.mark.parametrize('publisher', [None, 'Synthetic independent publisher', 'Альфа-Банк'])
def test_verified_pdf_preserves_format_and_exact_publisher_without_reassignment(publisher):
    source = {'id': 7, 'document': 'verified.pdf', 'page': 2, 'chunk_id': 4,
              'provenance': {'declared_format': 'PDF', 'format_verified': True,
                             'publisher': publisher, 'attribution_status': 'VERIFIED' if publisher else 'UNKNOWN',
                             'verification_reference': 'synthetic-curation-record'}}
    evidence = {'id': 12, 'evidence_type': 'PDF', 'document': 'verified.pdf',
                'page': 2, 'chunk_id': 4, 'text': 'Unchanged financial quotation', 'document_date': None}
    before = deepcopy((source, evidence))
    sources, rows = card_provenance([source], [evidence])
    assert sources == [source] and rows == [evidence]
    assert (source, evidence) == before
    assert sources[0]['provenance']['publisher'] == publisher


@pytest.mark.parametrize('change', ['document', 'page', 'chunk_id', 'missing_identity', 'string_true', 'conflict'])
def test_verified_format_cannot_be_borrowed_or_inferred(change):
    source = {'document': 'verified.pdf', 'page': 2, 'chunk_id': 4,
              'provenance': {'declared_format': 'PDF', 'format_verified': True, 'publisher': None}}
    row = {'document': 'verified.pdf', 'page': 2, 'chunk_id': 4, 'text': 'Exact original', 'evidence_type': 'PDF'}
    sources = [source]
    if change in ('document', 'page', 'chunk_id'):
        source[change] = 'other.pdf' if change == 'document' else 99
    elif change == 'missing_identity':
        source.pop('chunk_id'); row.pop('chunk_id')
    elif change == 'string_true':
        source['provenance']['format_verified'] = 'true'
    else:
        sources.append({**source, 'provenance': {'declared_format': 'TXT', 'format_verified': True}})
    before = deepcopy((sources, row))
    _, projected = card_provenance(sources, [row])
    assert projected == [{**row, 'evidence_type': 'DOCUMENT'}]
    assert (sources, row) == before


@pytest.mark.parametrize('value,name', [
    ('postgresql+asyncpg://u:p@production:5432/test_demo', 'test_demo'),
    ('postgresql+asyncpg://u:p@127.0.0.1:5432/production', 'production'),
    ('postgresql+asyncpg://u:p@127.0.0.1:5432/test_other', 'test_demo'),
])
def test_seed_target_guard_before_connection(value, name):
    import asyncio
    with pytest.raises(Exception):
        asyncio.run(seed(value, name))


def test_new_demo_compose_has_private_marked_database_and_no_ai():
    import json
    import os
    from pathlib import Path
    import subprocess
    root = Path(__file__).resolve().parents[2]
    config = json.loads(subprocess.check_output(
        ['docker', 'compose', '--profile', 'seed', '-f', str(root / 'compose.integration-demo.yml'), 'config', '--format', 'json'],
        env={**os.environ, 'INTEGRATION_DEMO_DB_PASSWORD': 'synthetic-unused-config-password'}))
    pg, backend, seed_config = [config['services'][s] for s in ['postgres', 'backend', 'seed']]
    assert 'ports' not in pg
    assert pg['environment']['POSTGRES_DB'] == 'test_integration_demo'
    assert backend['environment']['AI_MODE'] == 'demo'
    assert backend['environment']['LLM_API_KEY'] == ''
    assert seed_config['network_mode'] == 'service:postgres'
    assert '--apply' not in seed_config['command']
    assert any(v['source'].endswith('integration-demo-marker.sql') for v in pg['volumes'])


def test_seed_fixture_is_packaged_without_local_smoke_artifacts():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / 'backend/Dockerfile').read_text()
    ignore = (root / 'backend/.dockerignore').read_text()
    assert 'integration_demo.py' in dockerfile
    assert 'COPY fixtures/integration_demo.sql ./fixtures/integration_demo.sql' in dockerfile
    assert '!integration_demo.py' in ignore
    assert '!fixtures/integration_demo.sql' in ignore
    assert '!data' not in ignore and 'integration_demo_check' not in dockerfile
    sql = (root / 'backend/fixtures/integration_demo.sql').read_text(encoding='utf-8')
    assert 'synthetic-demo.txt' in sql and 'DEMO-003' in sql
