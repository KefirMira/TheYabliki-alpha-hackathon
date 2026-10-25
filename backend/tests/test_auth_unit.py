import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from main import app
from services.auth_service import HASHER, LoginLimiter, AuthService, normalized_login, token_digest, verify_password


def test_argon2id_random_salt_and_no_plaintext():
    password = 'synthetic-only-password'
    first, second = HASHER.hash(password), HASHER.hash(password)
    assert first != second and first.startswith('$argon2id$')
    assert password not in first and verify_password(first,password)
    assert not verify_password(first,'incorrect')
    assert not verify_password('malformed','incorrect')


@pytest.mark.parametrize('value,expected', [('  DEMO.User  ','demo.user'),('abc','abc'),('a',''),('../user',''),('x'*65,'')])
def test_login_normalization(value,expected):
    assert normalized_login(value)==expected


def test_limiter_expiry_capacity_and_cross_peer_login_limit():
    now=[1.0]
    limiter=LoginLimiter(clock=lambda:now[0],capacity=20)
    for i in range(5):limiter.check('same',str(i))
    with pytest.raises(HTTPException) as error:limiter.check('same','new-ip')
    assert error.value.status_code==429
    now[0]+=901
    limiter.check('same','new-ip')
    small=LoginLimiter(capacity=1)
    with pytest.raises(HTTPException):small.check('new','ip')
    assert len(small.entries)==0


def test_peer_limit_and_no_raw_bucket_values():
    limiter=LoginLimiter()
    for i in range(30):limiter.check('user'+str(i),'synthetic-peer')
    with pytest.raises(HTTPException):limiter.check('another','synthetic-peer')
    assert all(isinstance(key,bytes) and len(key)==32 for key in limiter.entries)


@pytest.mark.parametrize('token',['','x','x'*44,'a'*42+'!'])
def test_malformed_token_does_not_open_database(token):
    service=AuthService(lambda:pytest.fail('DB must not be used'))
    with pytest.raises(HTTPException) as error:asyncio.run(service.authenticate(token))
    assert error.value.status_code==401


BUSINESS_PATHS=[('GET','/api/companies/SYNTH-A'),('GET','/api/companies/SYNTH-A/insights'),
 ('GET','/api/companies/SYNTH-A/insights/1'),('POST','/api/companies/SYNTH-A/analyses'),
 ('POST','/api/companies/SYNTH-A/news/1/analyses'),('POST','/api/news'),
 ('POST','/api/analyze'),('POST','/api/analyze-rag'),('POST','/api/analyze-company'),
 ('GET','/api/me'),('POST','/api/auth/logout')]


@pytest.mark.parametrize('method,path',BUSINESS_PATHS)
def test_missing_auth_before_db_ai_or_body(monkeypatch,method,path):
    monkeypatch.delenv('DATABASE_URL',raising=False)
    monkeypatch.setenv('AI_MODE','full')
    with TestClient(app) as client:
        response=client.request(method,path,json={} if method=='POST' else None)
    assert response.status_code==401
    assert response.headers['www-authenticate']=='Bearer'


def test_login_validation_does_not_echo_credentials(monkeypatch):
    monkeypatch.delenv('DATABASE_URL',raising=False)
    secret='SYNTHETIC-DO-NOT-ECHO'
    with TestClient(app) as client:
        response=client.post('/api/auth/login',json={'login':secret*5,'password':secret,'extra':secret})
    assert response.status_code==422 and secret not in response.text
    assert response.json()['detail']['code']=='INVALID_LOGIN_INPUT'


def test_protected_openapi_documents_bearer():
    spec=app.openapi()
    assert spec["paths"]["/api/companies/{source_id}/news/{news_id}/dataset-analyses"]["post"]["security"]
    assert spec["paths"]["/api/companies/{source_id}/dataset-news"]["get"]["security"]
    for method,path in BUSINESS_PATHS:
        template=path.replace('SYNTH-A','{source_id}')
        if template.endswith('/insights/1'):template=template[:-1]+'{insight_id}'
        template=template.replace('/news/1/','/news/{news_id}/')
        assert spec['paths'][template][method.lower()]['security']
    assert 'security' not in spec['paths']['/api/auth/login']['post']


@pytest.mark.parametrize('authorization',['Bearer malformed','Basic synthetic','Bearer '+('x'*44)])
def test_malformed_http_auth_is_401_without_db(monkeypatch,authorization):
    monkeypatch.delenv('DATABASE_URL',raising=False)
    with TestClient(app) as client:
        response=client.get('/api/me',headers={'Authorization':authorization})
    assert response.status_code==401


def test_password_and_session_hash_are_not_in_model_repr():
    from schemas.auth import LoginInput, Principal
    from uuid import uuid4
    assert 'synthetic-password' not in repr(LoginInput(login='alice',password='synthetic-password'))
    assert 'synthetic-session-hash' not in repr(Principal(uuid4(),'alice','synthetic-session-hash'))


def test_cancelled_login_does_not_release_running_argon_worker(monkeypatch):
    import threading
    from contextlib import asynccontextmanager
    from services import auth_service as module
    started,release=threading.Event(),threading.Event()
    gate=threading.BoundedSemaphore(1)
    monkeypatch.setattr(module,'KDF_GATE',gate)
    monkeypatch.setattr(module,'LOGIN_LIMITER',LoginLimiter())
    monkeypatch.setattr('repositories.auth_repository.AuthRepository.user',AsyncMock(return_value=None))
    def verify(*args):
        started.set()
        release.wait(5)
        return False
    monkeypatch.setattr(module,'verify_password',verify)
    @asynccontextmanager
    async def sessions():yield object()
    async def scenario():
        service=AuthService(sessions)
        task=asyncio.create_task(service.login('unknown','synthetic','peer'))
        try:
            for _ in range(100):
                if started.is_set():break
                await asyncio.sleep(0.01)
            assert started.is_set()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):await task
            with pytest.raises(HTTPException) as error:await service.login('other','synthetic','peer')
            assert error.value.status_code==429
        finally:
            release.set()
            if not task.done():
                task.cancel()
            for _ in range(100):
                if gate.acquire(blocking=False):
                    gate.release()
                    break
                await asyncio.sleep(0.01)
            else:pytest.fail('KDF slot was not returned after worker exit')
    asyncio.run(scenario())
