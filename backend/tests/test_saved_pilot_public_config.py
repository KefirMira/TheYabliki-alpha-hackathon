"""Public local-demo credentials are intentional. Configuration checks, no SDK."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_PASSWORD = 'PulseDemo2026Viewer'
PUBLIC_DB_PASSWORD = '0123456789abcdef0123456789abcdef'


def resolved(tmp_path, polluted=False, network=False):
    if not shutil.which('docker'):
        pytest.skip('Docker Compose configuration parser required')
    env = {k:v for k,v in os.environ.items()
           if not k.startswith(('COMPOSE_', 'SAVED_PILOT_'))}
    if polluted:
        (tmp_path/'.env').write_text(
            'SAVED_PILOT_DB_PASSWORD=synthetic-wrong-old-value\n'
            'SAVED_PILOT_DEMO_PASSWORD=synthetic-wrong-login-value\n'
            'SAVED_PILOT_FRONTEND_PORT=18082\nSAVED_PILOT_PORT=18010\n'
            'SAVED_PILOT_SUBNET=192.168.248.0/24\n'
            'LLM_API_KEY=synthetic-unused-key\n', encoding='utf-8')
    command = ['docker','compose','--project-directory',str(tmp_path),
               '-f',str(ROOT/'compose.saved-pilot-demo.yml')]
    if network:
        command += ['-f',str(ROOT/'compose.saved-pilot.network.yml')]
    return json.loads(subprocess.check_output(command+['config','--format','json'],env=env))


@pytest.mark.parametrize('polluted', [False, True])
def test_no_env_or_old_env_cannot_change_public_credentials(tmp_path, polluted):
    config = resolved(tmp_path,polluted)
    assert config['name'] == 'pulse-saved-pilot-public'
    services = config['services']
    db = services['postgres']['environment']
    backend = services['backend']['environment']
    seed = services['seed']['environment']
    assert db['POSTGRES_PASSWORD'] == PUBLIC_DB_PASSWORD
    assert seed['SAVED_PILOT_DEMO_PASSWORD'] == PUBLIC_PASSWORD
    backend_url = make_url(backend['DATABASE_URL'])
    seed_url = make_url(seed['SAVED_PILOT_DATABASE_URL'])
    assert backend_url.password == seed_url.password == PUBLIC_DB_PASSWORD
    assert backend_url.username == seed_url.username == db['POSTGRES_USER']
    assert backend_url.database == seed_url.database == db['POSTGRES_DB']
    assert backend_url.host == 'postgres' and seed_url.host == '127.0.0.1'
    assert 'ports' not in services['postgres']
    assert '--verify-backend-connection' in services['seed']['command']
    for service in ['seed','backend']:
        assert services[service]['environment']['LLM_API_KEY'] == ''
        assert services[service]['environment']['LLM_BASE_URL'] == ''
        assert services[service]['environment']['LLM_MODEL'] == ''
    assert backend['AI_MODE'] == 'demo' and backend['DATASET_AI_TRANSPORT'] == 'fake'
    assert backend['SAVED_PILOT_OFFLINE'] == '1'
    for service in ['frontend','backend']:
        assert services[service]['ports'][0]['host_ip'] == '127.0.0.1'
    assert services['frontend']['ports'][0]['published'] == ('18082' if polluted else '8082')
    assert services['backend']['ports'][0]['published'] == ('18010' if polluted else '8010')
    assert not config['networks']['default'].get('ipam', {}).get('config')
    assert set(config['volumes']) == {'saved_pilot_public_v1282_data'}
    assert services['postgres']['volumes'][0]['source'] == 'saved_pilot_public_v1282_data'
    assert 'saved_pilot_pgdata' not in config['volumes']
    if not polluted:
        assert not (tmp_path/'.env').exists()


def test_network_override_is_explicit(tmp_path):
    config = resolved(tmp_path, polluted=True, network=True)
    assert config['networks']['default']['ipam']['config'] == [{'subnet':'192.168.248.0/24'}]


def test_quick_start_documents_public_demo_and_old_volume_isolation():
    readme = (ROOT/'README.md').read_text(encoding='utf-8')
    quick = readme.split('## Рекомендуемый запуск для жюри',1)[1].split('### Проверка запуска',1)[0]
    assert 'Copy-Item' not in quick
    assert 'docker compose -f compose.saved-pilot-demo.yml up --build -d --wait' in quick
    assert PUBLIC_PASSWORD in quick and 'synthetic-pilot-viewer' in quick
    assert 'без создания .env' in quick and 'read-only' in quick
    assert 'production' in quick and 'Интернет' in quick
    assert '16 UNKNOWN' in quick and '4 NEEDS_REVIEW' in quick
    assert 'saved_pilot_public_v1282_data' in readme
