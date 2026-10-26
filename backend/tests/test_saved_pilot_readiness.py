"""Offline synthetic tests: no PostgreSQL, SDK or secret-bearing logs."""
import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from main import app
from db.diagnostics import database_error_code
from db.job_schema import JOB_SCHEMA_SIGNATURE
from saved_pilot_demo import (main, verify_backend_connection,
                              BackendDatabaseCheckFailed, MARKER)


class AuthError(Exception):
    sqlstate = '28P01'


@pytest.mark.parametrize('state,code', [
    ('ready', 'READY'), ('no_factory', 'DATABASE_NOT_CONFIGURED'),
    ('missing_table', 'DATABASE_TABLE_MISSING'),
    ('identity', 'DATABASE_IDENTITY_SCHEMA_MISMATCH'),
    ('jobs', 'DATABASE_JOB_SCHEMA_MISMATCH'),
    ('matching', 'DATABASE_MATCH_SCHEMA_MISMATCH'),
    ('auth', 'DATABASE_AUTHENTICATION_FAILED'), ('timeout', 'DATABASE_TIMEOUT'),
    ('network', 'DATABASE_UNAVAILABLE'),
    ('jobs_error', 'DATABASE_UNAVAILABLE'), ('jobs_timeout', 'DATABASE_TIMEOUT'),
])
def test_saved_readiness_is_strict_and_sanitized(monkeypatch, state, code):
    monkeypatch.setenv('AI_MODE', 'demo')
    monkeypatch.setenv('SAVED_PILOT_OFFLINE', '1')
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setattr('api.readiness.rag_ready', lambda: pytest.fail('offline must not load RAG'))
    class Session:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def execute(self, sql, params=None):
            params = params or {}
            if 'signature' in params and state == 'jobs_error': raise OSError('secret')
            if 'signature' in params and state == 'jobs_timeout': raise TimeoutError('secret')
            if state == 'auth':
                error = RuntimeError('secret DSN and password must never leak')
                error.__cause__ = AuthError('secret')
                raise error
            if state == 'timeout': raise TimeoutError('secret')
            if state == 'network': raise OSError('secret DSN')
            value = True
            if 'name' in params:
                value = None if state == 'missing_table' else 'existing'
            elif 'signature' not in params:
                value = state != 'identity'
            elif params['signature'] == JOB_SCHEMA_SIGNATURE:
                value = state != 'jobs'
            else:
                value = state != 'matching'
            class Result:
                def scalar_one(self): return value
            return Result()
    with TestClient(app) as client:
        app.state.company_sessions = None if state == 'no_factory' else Session
        result = client.get('/ready')
    assert result.status_code == (200 if state == 'ready' else 503)
    body = result.json()
    assert body['checks'] == {'rag': False, 'llm_config': False, 'database': state == 'ready'}
    assert body['diagnostics'] == {'mode': 'saved-pilot-offline',
        'required_checks': ['database'], 'database_code': code}
    assert 'secret' not in result.text and '28P01' not in result.text


@pytest.mark.parametrize('state,expected', [('ready', None), ('auth', 'DATABASE_AUTHENTICATION_FAILED'),
    ('marker', 'DATABASE_ISOLATION_MARKER_MISMATCH'), ('network', 'DATABASE_UNAVAILABLE')])
def test_network_probe_is_readonly_same_credentials_and_disposed(monkeypatch, state, expected):
    url = 'postgresql+asyncpg://synthetic:' + 'a'*32 + '@127.0.0.1:5432/test_saved_pilot_demo'
    seen = []
    class Connection:
        async def __aenter__(self):
            if state == 'auth': raise AuthError('secret password')
            if state == 'network': raise OSError('secret DSN')
            return self
        async def __aexit__(self, *args): pass
        async def execute(self, query):
            seen.append(str(query))
            class Result:
                def mappings(self): return self
                def one(self): return {'name': 'test_saved_pilot_demo',
                    'marker': 'wrong' if state == 'marker' else MARKER}
            return Result()
    class Engine:
        def begin(self): return Connection()
        dispose = AsyncMock()
    engine = Engine()
    with patch('saved_pilot_demo.create_async_engine', return_value=engine) as create:
        if expected:
            with pytest.raises(BackendDatabaseCheckFailed) as error:
                asyncio.run(verify_backend_connection(url, 'test_saved_pilot_demo'))
            assert error.value.code == expected
            assert 'secret' not in str(error.value)
        else:
            asyncio.run(verify_backend_connection(url, 'test_saved_pilot_demo'))
        target = create.call_args.args[0]
        assert target.host == 'postgres' and target.username == 'synthetic'
        assert target.password == 'a'*32 and target.database == 'test_saved_pilot_demo'
        assert create.call_args.kwargs['hide_parameters'] is True
    engine.dispose.assert_awaited_once()
    assert all(q.startswith(('SELECT', 'SET TRANSACTION READ ONLY')) for q in seen)


def test_auth_failure_stops_cli_before_import_and_redacts(monkeypatch, capsys):
    monkeypatch.setenv('SAVED_PILOT_DEMO_PASSWORD', 'Synthetic-password-for-test')
    monkeypatch.setenv('SAVED_PILOT_DATABASE_URL', 'secret-dsn')
    with patch('saved_pilot_demo.verify_backend_connection', new_callable=AsyncMock,
               side_effect=BackendDatabaseCheckFailed('DATABASE_AUTHENTICATION_FAILED')), \
         patch('saved_pilot_demo.import_pilot') as writer:
        assert main(['--expected-database', 'test_saved_pilot_demo', '--apply',
                     '--confirm-isolated', '--password-env', '--verify-backend-connection']) == 1
        writer.assert_not_called()
    assert json.loads(capsys.readouterr().out) == {
        'code': 'SAVED_PILOT_BACKEND_DATABASE_CHECK_FAILED',
        'reason': 'DATABASE_AUTHENTICATION_FAILED'}


def test_wrapped_error_cycles_are_bounded():
    error = RuntimeError('secret')
    error.__cause__ = error
    assert database_error_code(error) == 'DATABASE_UNAVAILABLE'
