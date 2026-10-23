from dataclasses import replace
import json
import sqlite3

import pytest

from parser.config import Config
from parser.collector import collect_once
from parser.http_source import HTTPRSS, SourceError
from parser.backend_client import Delivery
from parser.state import State
from test_http_source import Transport, FakeResponse
from test_state_delivery import Clock, FakeBackend, rows, publication


def configured(**overrides):
    return replace(Config.from_env({'PARSER_SOURCE_MODE':'http','PARSER_HTTP_RSS_ENABLED':'1',
        'PARSER_RSS_URL':'https://feed.example.invalid/rss','PARSER_SOURCE_NAME':'synthetic-demo',
        'PARSER_SOURCE_INTERVAL':'1'}),**overrides)


def collect(config,clock,backend,transport,**kwargs):
    fetch=HTTPRSS(transport=transport,resolver=lambda *args:['8.8.8.8'],wall_clock=clock)
    return collect_once(config,backend,clock=clock,wait=clock.wait,random_value=lambda:.5,fetch=fetch,**kwargs)


def test_http_checkpoint_restart_304_and_duplicate_guid():
    config,clock=configured(),Clock()
    collect(config,clock,FakeBackend([Delivery('timeout')]),Transport(FakeResponse(headers={
        'ETag':'"v1"','Last-Modified':'Thu, 01 Jan 2026 00:00:00 GMT'})))
    assert len(rows(config))==1 and rows(config)[0]['status']=='retry'
    assert 'LOCAL_PAYLOAD_CHANGED' in json.loads(rows(config)[0]['issues'])
    clock.now+=2
    transport=Transport(FakeResponse(304))
    collect(config,clock,FakeBackend([Delivery('duplicate',200,42)]),transport)
    assert transport.calls[0][2]['If-None-Match']=='"v1"'
    assert transport.calls[0][2]['If-Modified-Since']=='Thu, 01 Jan 2026 00:00:00 GMT'
    assert rows(config)[0]['news_id']==42 and rows(config)[0]['attempts']==2
    assert rows(config,'sources')[0]['etag']=='"v1"'


def test_http_reports_do_not_expose_untrusted_guid():
    from test_http_source import XML
    config,clock=configured(),Clock()
    secret_guid='https://example.invalid/private?token=synthetic-secret'
    body=XML.replace(b'SYNTH-HTTP-1',secret_guid.encode())
    report=collect(config,clock,FakeBackend([Delivery('created',201,9)]),Transport(FakeResponse(body=body)))
    assert secret_guid not in json.dumps(report)
    assert report['items'][-1]['source_id'] is None
    assert report['items'][-1]['identity_digest']
    assert secret_guid in rows(config)[0]['payload']  # Exact identity still reaches backend.


@pytest.mark.parametrize('status',[429,500,503])
def test_http_error_backoff_retry_after_and_old_queue_delivery(status):
    config,clock=configured(),Clock()
    collect(config,clock,FakeBackend([Delivery('timeout')]),Transport(FakeResponse(headers={'ETag':'"v1"'})))
    clock.now+=2
    report=collect(config,clock,FakeBackend([Delivery('created',201,7)]),
        Transport(FakeResponse(status,headers={'Retry-After':'120'})))
    assert report['source_error']=='RSS_HTTP_'+str(status)
    assert rows(config)[0]['status']=='delivered'
    state=rows(config,'sources')[0]
    assert state['etag']=='"v1"' and state['next_fetch']==clock.now+120
    assert state['fetch_failures']==1
    backend=FakeBackend([])
    deferred=collect(config,clock,backend,Transport())
    assert deferred['source_fetch_status']=='deferred'
    assert not backend.calls


def test_http_exhaustion_and_explicit_reset_preserve_queue_and_deadline():
    config,clock=configured(max_attempts=2),Clock()
    for _ in range(2):
        report=collect(config,clock,FakeBackend([]),Transport(TimeoutError()))
        clock.now=rows(config,'sources')[0]['next_fetch']
    assert report['source_fetch']['fetch_blocked']==1
    blocked=collect(config,clock,FakeBackend([]),Transport())
    assert blocked['source_error']=='RSS_SOURCE_BLOCKED'
    reset=collect(config,clock,FakeBackend([Delivery('created',201,9)]),Transport(FakeResponse()),reset_source=True)
    assert reset['source_fetch']['fetch_blocked']==0
    assert rows(config)[0]['news_id']==9


def test_crash_after_http_enqueue_does_not_advance_checkpoint():
    config,clock=configured(),Clock()
    def crash():raise RuntimeError('Synthetic process crash')
    with pytest.raises(RuntimeError):
        collect(config,clock,FakeBackend([]),Transport(FakeResponse(headers={'ETag':'"v2"'})),after_enqueue=crash)
    assert len(rows(config))==1 and rows(config,'sources')[0]['etag'] is None
    # Restart before the next fetch: durable outbox is still delivered.
    report=collect(config,clock,FakeBackend([Delivery('created',201,11)]),Transport())
    assert report['source_fetch_status']=='deferred' and rows(config)[0]['news_id']==11
    clock.now+=2
    transport=Transport(FakeResponse(headers={'ETag':'"v2"'}))
    collect(config,clock,FakeBackend([]),transport)
    assert 'If-None-Match' not in transport.calls[0][2]
    assert rows(config,'sources')[0]['etag']=='"v2"'


def test_stale_fetch_owner_cannot_enqueue_or_checkpoint():
    config,clock=configured(),Clock()
    first,second=State(config.state_path),State(config.state_path)
    try:
        first.acquire(config,'old',clock())
        def takeover():
            clock.now+=config.lease_seconds+1
            assert second.acquire(config,'new',clock())
            return []
        takeover()
        with pytest.raises(RuntimeError,match='lease lost'):
            first.enqueue(config.source_name,[publication()],clock(),config=config,owner='old')
        assert not second.rows(config.source_name)
    finally:first.close();second.close()


def test_fetch_failure_between_download_and_enqueue_preserves_validators(monkeypatch):
    config,clock=configured(),Clock()
    original=State.enqueue
    def crash(*args,**kwargs):raise sqlite3.OperationalError('Synthetic disk failure')
    monkeypatch.setattr(State,'enqueue',crash)
    with pytest.raises(sqlite3.OperationalError):
        collect(config,clock,FakeBackend([]),Transport(FakeResponse(headers={'ETag':'"v3"'})))
    assert rows(config)==[] and rows(config,'sources')[0]['etag'] is None
    monkeypatch.setattr(State,'enqueue',original)
    clock.now+=2
    collect(config,clock,FakeBackend([Delivery('created',201,4)]),Transport(FakeResponse(headers={'ETag':'"v3"'})))
    assert rows(config)[0]['news_id']==4


@pytest.mark.parametrize('env',[{'PARSER_SOURCE_MODE':'invalid'}, {'PARSER_SOURCE_MODE':'http'},
    {'PARSER_HTTP_RSS_ENABLED':'yes'}, {'PARSER_RSS_MAX_BYTES':'1048577'}, {'PARSER_RSS_MAX_REDIRECTS':'6'}])
def test_http_requires_explicit_valid_configuration(env):
    with pytest.raises(ValueError):Config.from_env(env)


def test_existing_sqlite_v1_upgrades_without_queue_loss():
    config=Config.from_env({})
    state=State(config.state_path)
    state.acquire(config,'synthetic',1000)
    state.enqueue(config.source_name,[publication()],1000)
    state.release(config.source_name,'synthetic')
    state.close()
    with sqlite3.connect(config.state_path) as db:
        for column in ('fetch_failures','fetch_blocked','next_fetch'):
            db.execute('ALTER TABLE sources DROP COLUMN '+column)
        db.execute('PRAGMA user_version=1')
    upgraded=State(config.state_path)
    try:
        assert len(upgraded.rows(config.source_name))==1
        assert upgraded.db.execute('PRAGMA user_version').fetchone()[0]==2
    finally:upgraded.close()
