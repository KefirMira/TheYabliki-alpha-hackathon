"""Runner argv tests use a fake Docker command; config checks never start services."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
NETWORK = 'theyabliki-db-check-1a832d244c5f_default'
HARNESS = r'''
param([string]$Runner, [string]$Override)
$ErrorActionPreference='Stop'
$global:CapturedCalls=[Collections.Generic.List[object]]::new()
function global:docker {
    $global:CapturedCalls.Add(@($args))
    $global:LASTEXITCODE=0
    if ($args -contains 'exec') { $global:LASTEXITCODE=19 }
}
$caught=$null
try {
    if ($Override) { & $Runner -ComposeOverride $Override } else { & $Runner }
} catch { $caught=$_.Exception.Message }
Write-Output ('MOCK_RESULT='+(@{calls=@($global:CapturedCalls.ToArray());error=$caught} | ConvertTo-Json -Depth 8 -Compress))
'''


@pytest.mark.parametrize('runner', ['backend/tests/run-profile-tests.ps1', 'database/tests/run.ps1'])
@pytest.mark.parametrize('mode', ['normal', 'override', 'missing', 'directory'])
def test_runner_uses_same_compose_files_including_finally(tmp_path, runner, mode):
    shell = shutil.which('pwsh') or shutil.which('powershell')
    if not shell:
        pytest.skip('PowerShell required for runner argv tests')
    repo = tmp_path / 'repository with spaces'
    script = repo / runner
    script.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / runner, script)
    python = repo / '.venv/Scripts/python.exe'
    python.parent.mkdir(parents=True)
    python.touch()  # Never executed: injected SQL failure precedes pytest.
    for file in ('compose.test.yml', 'schema.sql', 'migrations/002_pulse_features.sql',
                 'migrations/003_integrity.sql', 'migrations/004_news_external_identity.sql',
                 'migrations/005_saved_news_analysis_jobs.sql', 'tests/fixtures/base.sql', 'tests/fingerprint.sql'):
        target = repo / 'database' / file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('-- synthetic runner stub', encoding='utf-8')
    override = tmp_path / 'override with spaces.yml'
    if mode == 'override':
        override.write_text('networks: {}', encoding='utf-8')
    elif mode == 'directory':
        override.mkdir()
    harness = tmp_path / 'mock docker.ps1'
    harness.write_text(HARNESS, encoding='utf-8-sig')
    command = [shell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(harness), str(script)]
    if mode != 'normal':
        command.append(str(override))
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', check=True)
    payload = json.loads(next(line.removeprefix('MOCK_RESULT=') for line in result.stdout.splitlines()
                              if line.startswith('MOCK_RESULT=')))
    if mode in {'missing', 'directory'}:
        assert payload['calls'] == []
        assert payload['error'].startswith('Compose override not found:')
        return
    assert payload['error'].startswith('Docker Compose failed:')  # Expected injected failure.
    calls = payload['calls']
    assert len(calls) == 4  # config, up, first SQL exec, finally stop.
    for call in calls:
        assert call[:2] == ['compose', '-p']
        files = [call[index + 1] for index, value in enumerate(call) if value == '-f']
        # SQL's own -f is additional only in exec, and must not affect Compose argv.
        expected = [str(repo / 'database/compose.test.yml')]
        if mode == 'override':
            expected.append(str(override.resolve()))
        assert [str(Path(file).resolve()) for file in files[:len(expected)]] == expected
        assert call[3:3 + 2 * len(expected):2] == ['-f'] * len(expected)
        assert not any(value in {'down', 'rm', 'prune', '--volumes'} for value in call)
    assert calls[-1][-1] == 'stop'
    assert len({call[2] for call in calls}) == 1


@pytest.mark.parametrize('with_override', [False, True])
def test_resolved_database_config_network_and_project_volume(tmp_path, with_override):
    if not shutil.which('docker'):
        pytest.skip('Docker CLI required for Compose config only')
    command = ['docker', 'compose', '-p', 'pulse-override-config-test', '-f', str(ROOT / 'database/compose.test.yml')]
    if with_override:
        override = tmp_path / 'external network with spaces.yml'
        override.write_text(f'networks:\n  default:\n    external: true\n    name: {NETWORK}\n', encoding='utf-8')
        command += ['-f', str(override)]
    config = json.loads(subprocess.check_output(command + ['config', '--format', 'json'],
                        env={**os.environ, 'DB_TEST_PASSWORD': 'synthetic-config-only'}))
    network = config['networks']['default']
    assert bool(network.get('external')) is with_override
    assert network['name'] == (NETWORK if with_override else 'pulse-override-config-test_default')
    assert list(config['services']) == ['postgres']
    assert not config['services']['postgres'].get('container_name')
    volume = config['volumes']['audit_data']
    assert volume['name'] == 'pulse-override-config-test_audit_data' and not volume.get('external')
