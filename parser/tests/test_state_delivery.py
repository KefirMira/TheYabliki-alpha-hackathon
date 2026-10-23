"""Durability/recovery with a real SQLite file and synthetic HTTP responses."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from email.utils import formatdate
import importlib
import json
import socket
import sqlite3
from threading import Barrier, Event

import httpx
import pytest

from parser.backend_client import BackendClient, Delivery, retry_after
from parser.collector import collect_once, poll
from parser.config import Config
from parser.models import NewsPayload
from parser.rss import Item
from parser.source import Scan
from parser.state import State


class Clock:
    def __init__(self):
        self.now = 1000.
    def __call__(self):
        return self.now
    def wait(self, seconds):
        self.now += seconds + .000001
        return False


def publication(key='SYNTH-1', content='Invented content'):
    return Item(1, NewsPayload(title='Synthetic', content=content,
                              source_name='synthetic-demo', source_id=key), [])


def source(config, headers):
    return Scan(items=[publication()])


class FakeBackend:
    def __init__(self, deliveries):
        self.deliveries = iter(deliveries)
        self.calls = []
    def deliver(self, payload):
        self.calls.append(payload)
        return next(self.deliveries)
    def close(self):
        pass


def run(config, clock, backend, **kw):
    return collect_once(config, backend, clock=clock, wait=clock.wait,
                        random_value=lambda: .5, fetch=kw.pop('fetch', source), **kw)


def rows(config, table='queue'):
    with sqlite3.connect(config.state_path) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute('SELECT * FROM ' + table)]


def test_unavailable_restart_recovery_and_no_redelivery():
    config, clock = Config.from_env({}), Clock()
    first = run(config, clock, FakeBackend([Delivery('network_error')]))
    assert first['queue_counts'] == {'retry': 1}
    saved = rows(config)[0]
    assert saved['attempts'] == 1 and saved['next_attempt'] == 1001.5
    waiting = FakeBackend([])
    run(config, clock, waiting)
    assert not waiting.calls
    clock.now = saved['next_attempt']
    backend = FakeBackend([Delivery('duplicate', 200, 12, ['CONTENT_MISMATCH'])])
    assert run(config, clock, backend)['queue_counts'] == {'delivered': 1}
    saved = rows(config)[0]
    assert saved['news_id'] == 12 and json.loads(saved['diagnostics']) == ['CONTENT_MISMATCH']
    assert saved['attempts'] == 2 and len(rows(config, 'attempts')) == 2
    run(config, clock, FakeBackend([]))  # New State/connection, same on-disk database.
    assert rows(config)[0]['attempts'] == 2


@pytest.mark.parametrize('status', ['timeout', 'network_error', 'rate_limited', 'unavailable', 'temporary_error'])
def test_exhaustion_is_retained(status):
    config, clock = replace(Config.from_env({}), max_attempts=2), Clock()
    backend = FakeBackend([Delivery(status), Delivery(status)])
    run(config, clock, backend)
    clock.now += 20
    report = run(config, clock, backend)
    assert report['queue_counts'] == {'dead_letter': 1}
    clock.now += 9999
    run(config, clock, backend)
    assert len(backend.calls) == 2 and len(rows(config)) == 1


@pytest.mark.parametrize('code,status', [(409, 'conflict'), (422, 'invalid_data')])
def test_manual_errors_never_retry(code, status):
    config, clock = Config.from_env({}), Clock()
    backend = FakeBackend([Delivery(status, code, diagnostics=['TEST_REASON'])])
    run(config, clock, backend)
    clock.now += 1e6
    run(config, clock, backend)
    saved = rows(config)[0]
    assert saved['status'] == 'failed' and saved['attempts'] == 1
    assert saved['http_status'] == code and saved['last_error'] == status
    assert json.loads(saved['diagnostics']) == ['TEST_REASON']


@pytest.mark.parametrize('hint,deadline', [('120', 1120), (formatdate(1300, usegmt=True), 1300),
    (formatdate(900, usegmt=True), 1000), ('nonsense', None), ('-1', None), (None, None)])
def test_retry_after_formats(hint, deadline):
    assert retry_after(hint, 1000) == deadline


def test_429_http_hint_persisted_and_blocks_early_requests():
    config, clock = Config.from_env({}), Clock()
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(429, headers={'Retry-After': '120'}))) as http:
        backend = BackendClient(config, http, clock=clock)
        report = run(config, clock, backend)
    assert report['queue_counts'] == {'retry': 1}
    assert rows(config)[0]['next_attempt'] == 1120
    clock.now = 1119
    run(config, clock, FakeBackend([]))
    clock.now = 1120
    run(config, clock, FakeBackend([Delivery('created', 201, 9)]))
    assert rows(config)[0]['news_id'] == 9


def test_duplicate_guid_and_date_independence():
    config, clock = Config.from_env({}), Clock()
    def repeated(config, headers):
        return Scan(items=[publication(), replace(publication(), index=2), replace(publication('SYNTH-2'), index=3)])
    backend = FakeBackend([Delivery('created', 201, 1), Delivery('created', 201, 2)])
    run(config, clock, backend, fetch=repeated)
    assert len(rows(config)) == 2 and len(backend.calls) == 2
    assert all(payload.published_at is None for payload in backend.calls)


def test_url_fallback_identity_is_not_content_hash():
    a = NewsPayload(title='Synthetic', content='Same', source_name='synthetic-demo', url='https://example.invalid/A')
    b = a.model_copy(update={'url': 'https://example.invalid/B'})
    assert State.key(a) != State.key(b)
    assert State.key(a) == State.key(a.model_copy(update={'content': 'Changed'}))


def test_crash_after_enqueue_before_checkpoint_keeps_queue():
    config, clock = Config.from_env({}), Clock()
    def crash():
        raise RuntimeError('Simulated process failure after durable enqueue')
    with pytest.raises(RuntimeError):
        run(config, clock, FakeBackend([]), after_enqueue=crash)
    assert rows(config)[0]['status'] == 'pending'
    assert rows(config, 'sources')[0]['last_success'] is None
    run(config, clock, FakeBackend([Delivery('created', 201, 3)]))
    assert len(rows(config)) == 1 and rows(config)[0]['news_id'] == 3
    assert rows(config, 'sources')[0]['last_success'] == clock.now


def test_enqueue_batch_is_atomic(monkeypatch):
    config, clock = Config.from_env({}), Clock()
    state = State(config.state_path)
    assert state.acquire(config, 'test', clock())
    state.db.execute("CREATE TRIGGER test_failure BEFORE INSERT ON queue WHEN NEW.item_key='id:SYNTH-2' BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        state.enqueue(config.source_name, [publication(), publication('SYNTH-2')], clock())
    assert state.rows(config.source_name) == []
    assert state.db.execute('SELECT last_success FROM sources').fetchone()[0] is None
    state.close()


def test_no_simultaneous_source_scan_and_expired_lease_recovery():
    config, clock = Config.from_env({}), Clock()
    first, second = State(config.state_path), State(config.state_path)
    try:
        assert first.acquire(config, 'first-process', clock())
        assert not second.acquire(config, 'second-process', clock())
        report = run(config, clock, FakeBackend([]), fetch=lambda *args: pytest.fail('Concurrent scan'))
        assert report['source_busy']
        first.enqueue(config.source_name, [publication()], clock())
        row, _ = first.claim(config, 'first-process', clock(), set())
        assert row is not None
        # Simulate SIGKILL: no release; another connection/process waits for expiry.
        clock.now += config.lease_seconds + 1
        assert second.acquire(config, 'second-process', clock())
        with pytest.raises(RuntimeError, match='lease lost'):
            first.finish(config, 'first-process', row, Delivery('created', 201, 88), clock(), .5)
        assert second.rows(config.source_name)[0]['status'] == 'retry'
        assert second.rows(config.source_name)[0]['attempts'] == 1
        second.release(config.source_name, 'second-process')
    finally:
        first.close()
        second.close()
    run(config, clock, FakeBackend([Delivery('duplicate', 200, 88)]))
    assert rows(config)[0]['status'] == 'delivered'
    assert rows(config, 'attempts')[0]['result'] == 'uncertain'


def test_concurrent_connections_only_one_source_owner():
    config, clock, barrier = Config.from_env({}), Clock(), Barrier(2)
    State(config.state_path).close()
    def contender(owner):
        state = State(config.state_path)
        try:
            barrier.wait(timeout=5)
            return state.acquire(config, owner, clock())
        finally:
            state.close()  # Keep lease until the other process has attempted acquisition.
    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(contender, ['process-a', 'process-b']))
    assert sorted(outcomes) == [False, True]


def test_crashed_last_attempt_becomes_dead_letter():
    config, clock = replace(Config.from_env({}), max_attempts=1), Clock()
    state = State(config.state_path)
    state.acquire(config, 'crashed', clock())
    state.enqueue(config.source_name, [publication()], clock())
    state.claim(config, 'crashed', clock(), set())
    state.close()
    clock.now += config.lease_seconds + 1
    backend = FakeBackend([])
    assert run(config, clock, backend)['queue_counts'] == {'dead_letter': 1}
    assert not backend.calls


def test_304_preserves_pending_queue_and_validators():
    config, clock = Config.from_env({}), Clock()
    def initial(config, headers):
        assert headers == {}
        return Scan(items=[publication()], etag='"synthetic-v1"', last_modified='Thu, 01 Jan 2026 00:00:00 GMT')
    run(config, clock, FakeBackend([Delivery('timeout')]), fetch=initial)
    clock.now += 10
    def unchanged(config, headers):
        assert headers['If-None-Match'] == '"synthetic-v1"'
        assert 'If-Modified-Since' in headers
        return Scan(status=304)
    run(config, clock, FakeBackend([Delivery('created', 201, 42)]), fetch=unchanged)
    assert rows(config)[0]['news_id'] == 42
    assert rows(config, 'sources')[0]['etag'] == '"synthetic-v1"'


def test_source_failure_still_drains_saved_queue():
    config, clock = Config.from_env({}), Clock()
    run(config, clock, FakeBackend([Delivery('timeout')]))
    clock.now += 10
    def unavailable(*args):
        raise OSError('Synthetic file temporarily absent')
    report = run(config, clock, FakeBackend([Delivery('created', 201, 7)]), fetch=unavailable)
    assert report['source_error'] == 'OSError' and rows(config)[0]['news_id'] == 7


def test_rate_limit_survives_connection_restart():
    config, clock = replace(Config.from_env({}), request_interval=2), Clock()
    state = State(config.state_path)
    assert state.acquire(config, 'one', clock())
    state.enqueue(config.source_name, [publication(), publication('SYNTH-2')], clock())
    first, _ = state.claim(config, 'one', clock(), set())
    state.finish(config, 'one', first, Delivery('created', 201, 1), clock(), .5)
    state.release(config.source_name, 'one')
    state.close()
    state = State(config.state_path)
    try:
        assert state.acquire(config, 'two', clock())
        assert state.claim(config, 'two', clock(), set()) == (None, 2)
    finally:
        state.close()


def test_poll_stops_during_interruptible_wait():
    stop, seen = Event(), []
    config = Config.from_env({})
    def collect(config, stop):
        seen.append(config)
        stop.set()
        return {'synthetic': True}
    reports = []
    poll(config, stop, reports.append, collect=collect)
    assert len(seen) == 1 and reports == [{'synthetic': True}]


def test_cli_poll_signal_handler_and_restore(monkeypatch):
    import signal
    from parser import __main__ as cli
    previous = signal.getsignal(signal.SIGTERM)
    def polling(config, stop, on_report):
        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        assert stop.is_set()
    monkeypatch.setattr(cli, 'poll', polling)
    assert cli.main(['--poll']) == 0
    assert signal.getsignal(signal.SIGTERM) == previous


@pytest.mark.parametrize('random_value,factor', [(0, .5), (.5, .75), (1, 1)])
def test_backoff_exponential_cap_and_jitter(random_value, factor):
    config, clock = replace(Config.from_env({}), backoff_base=2, backoff_cap=3), Clock()
    state = State(config.state_path)
    try:
        state.acquire(config, 'test', clock())
        state.enqueue(config.source_name, [publication()], clock())
        for expected in (2 * factor, 3 * factor, 3 * factor):
            row, _ = state.claim(config, 'test', clock(), set())
            state.finish(config, 'test', row, Delivery('timeout'), clock(), random_value)
            saved = state.rows(config.source_name)[0]
            assert saved['next_attempt'] - clock.now == expected
            clock.now = saved['next_attempt']
    finally:
        state.close()


def test_stop_during_rate_wait_preserves_remaining_queue():
    config, clock, stop = replace(Config.from_env({}), request_interval=2), Clock(), Event()
    def stop_wait(seconds):
        stop.set()
        return True
    backend = FakeBackend([Delivery('created', 201, 1)])
    collect_once(config, backend, clock=clock, stop=stop, wait=stop_wait,
                 fetch=lambda *args: Scan(items=[publication(), publication('SYNTH-2')]))
    assert len(backend.calls) == 1
    assert sorted(row['status'] for row in rows(config)) == ['delivered', 'pending']


@pytest.mark.parametrize('key,value', [('PARSER_MAX_ATTEMPTS', '0'), ('PARSER_MAX_ATTEMPTS', '21'),
    ('PARSER_BACKOFF_BASE', 'nan'), ('PARSER_BACKOFF_CAP', '0'), ('PARSER_POLL_INTERVAL', '0'),
    ('PARSER_REQUEST_INTERVAL', '0'), ('PARSER_LEASE_SECONDS', '1'), ('PARSER_STATE_PATH', 'fixtures/synthetic.xml')])
def test_invalid_state_settings(key, value):
    with pytest.raises(ValueError):
        Config.from_env({key: value})


def test_llm_and_external_network_are_blocked():
    for sdk in ['openai', 'anthropic']:
        with pytest.raises(ImportError):
            importlib.import_module(sdk)
    with pytest.raises(AssertionError, match='External DNS'):
        socket.getaddrinfo('example.com', 443)
    with socket.socket() as sock:
        with pytest.raises(AssertionError, match='External network'):
            sock.connect(('192.0.2.1', 443))
    with socket.socket(type=socket.SOCK_DGRAM) as sock:
        with pytest.raises(AssertionError, match='External network'):
            sock.sendto(b'synthetic', ('192.0.2.1', 53))
