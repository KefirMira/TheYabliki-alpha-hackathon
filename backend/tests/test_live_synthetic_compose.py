"""Separate jury live deployment config; NEVER performs LLM or starts containers."""
import json,os,subprocess
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]

def config(tmp_path,filename,key='synthetic-not-a-real-key'):
    content=(ROOT/'.env.example').read_text().replace('LLM_API_KEY=','LLM_API_KEY='+key,1)
    (tmp_path/'.env').write_text(content)
    env={k:v for k,v in os.environ.items() if not k.startswith(('LLM_','LIVE_SYNTHETIC_','AI_MODE','SAVED_PILOT_','COMPOSE_'))}
    return subprocess.run(['docker','compose','--project-directory',str(tmp_path),'--env-file',str(tmp_path/'.env'),'-f',str(ROOT/filename),'config','--format','json'],env=env,text=True,capture_output=True)

def test_live_isolated_runtime_key_and_no_frontend_or_seed_secret(tmp_path):
    r=config(tmp_path,'compose.live-synthetic.yml');assert r.returncode==0,r.stderr
    c=json.loads(r.stdout);services=c['services'];env=services['backend']['environment']
    assert c['name']=='pulse-live-synthetic-demo'
    assert set(c['volumes'])=={'live_synthetic_demo_data'}
    assert env['LIVE_SYNTHETIC_ANALYSIS_ENABLED']=='true' and env['LIVE_SYNTHETIC_MAX_REQUESTS']=='5'
    assert env['AI_MODE']=='full' and env['SAVED_PILOT_OFFLINE']=='0'
    assert env['LLM_API_KEY']=='synthetic-not-a-real-key'
    assert services['postgres']['environment']['POSTGRES_DB']=='test_live_synthetic_demo'
    assert 'ports' not in services['postgres']
    assert services['seed']['environment']['LLM_API_KEY']==''
    assert 'environment' not in services['frontend']
    assert not services['backend']['build'].get('args')
    assert all(p['host_ip']=='127.0.0.1' for service in ['frontend','backend'] for p in services[service]['ports'])
    probe=services['backend']['healthcheck']['test'][-1]
    assert 'asyncpg.connect' in probe and 'auth_user_companies' in probe and 'enabled()' in probe
    assert '.complete(' not in probe and '/ready' not in probe

def test_live_missing_key_fails_before_start(tmp_path):
    r=config(tmp_path,'compose.live-synthetic.yml',key='')
    assert r.returncode!=0 and 'LLM_API_KEY' in r.stderr

@pytest.mark.parametrize('key',['','synthetic-not-a-real-key'])
def test_offline_ignores_live_env_and_key(tmp_path,key):
    r=config(tmp_path,'compose.saved-pilot-demo.yml',key=key);assert r.returncode==0,r.stderr
    services=json.loads(r.stdout)['services'];env=services['backend']['environment']
    assert env['LLM_API_KEY']==env['LLM_BASE_URL']==env['LLM_MODEL']==''
    assert env['AI_MODE']=='demo' and env['SAVED_PILOT_OFFLINE']=='1'
    assert env.get('LIVE_SYNTHETIC_ANALYSIS_ENABLED')!='true'
    assert services['seed']['environment']['SAVED_PILOT_DEMO_PASSWORD']=='PulseDemo2026Viewer'
