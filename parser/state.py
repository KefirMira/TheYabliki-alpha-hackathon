"""Private SQLite outbox. No PostgreSQL dependencies or backend imports."""
from contextlib import contextmanager
import json
import sqlite3

from .models import NewsPayload

RETRYABLE = {"timeout", "network_error", "rate_limited", "unavailable", "temporary_error"}


class State:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in {0, 1, 2}:
            self.db.close()
            raise ValueError("Unsupported parser state version")
        self.db.executescript("""
        BEGIN IMMEDIATE;
        CREATE TABLE IF NOT EXISTS sources (
          name TEXT PRIMARY KEY, locator TEXT NOT NULL, etag TEXT, last_modified TEXT,
          last_success REAL, last_error TEXT, owner TEXT, lease_until REAL);
        CREATE TABLE IF NOT EXISTS queue (
          id INTEGER PRIMARY KEY, source TEXT NOT NULL REFERENCES sources(name),
          item_key TEXT NOT NULL, payload TEXT NOT NULL, issues TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('pending','inflight','retry','delivered','failed','dead_letter')),
          attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL,
          news_id INTEGER, diagnostics TEXT NOT NULL DEFAULT '[]', http_status INTEGER,
          last_error TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL,
          UNIQUE(source,item_key));
        CREATE INDEX IF NOT EXISTS queue_due ON queue(source,status,next_attempt,id);
        CREATE TABLE IF NOT EXISTS attempts (
          queue_id INTEGER NOT NULL REFERENCES queue(id), number INTEGER NOT NULL,
          started_at REAL NOT NULL, finished_at REAL, result TEXT NOT NULL,
          http_status INTEGER, diagnostics TEXT NOT NULL DEFAULT '[]',
          PRIMARY KEY(queue_id,number));
        CREATE TABLE IF NOT EXISTS rate_limits (endpoint TEXT PRIMARY KEY, next_request REAL NOT NULL);
        COMMIT;
        """)
        with self.transaction():
            columns={row[1] for row in self.db.execute('PRAGMA table_info(sources)')}
            for name,definition in [('fetch_failures','INTEGER NOT NULL DEFAULT 0'),
                                    ('next_fetch','REAL NOT NULL DEFAULT 0'),
                                    ('fetch_blocked','INTEGER NOT NULL DEFAULT 0')]:
                if name not in columns:self.db.execute(f'ALTER TABLE sources ADD COLUMN {name} {definition}')
            self.db.execute('PRAGMA user_version=2')

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def acquire(self, config, owner, now):
        with self.transaction():
            locator=config.rss_url if config.source_mode=='http' else str(config.rss_path)
            self.db.execute("INSERT OR IGNORE INTO sources(name,locator) VALUES (?,?)",
                            (config.source_name, locator))
            source = self.db.execute("SELECT * FROM sources WHERE name=?", (config.source_name,)).fetchone()
            if source['locator']!=locator and (config.source_mode=='http' or source['locator'].startswith(('http://','https://'))):
                raise ValueError('RSS source_name is already bound to a different locator')
            if source['owner'] and source['lease_until'] > now:
                return False
            self.db.execute("UPDATE sources SET owner=?,lease_until=?,locator=? WHERE name=?",
                            (owner, now + config.lease_seconds, locator, config.source_name))
            # An expired process might have sent a request before dying. Count its attempt,
            # retain uncertainty, and redeliver using the same backend identity.
            self.db.execute("UPDATE attempts SET result='uncertain',finished_at=? WHERE result='inflight' AND queue_id IN (SELECT id FROM queue WHERE source=?)",
                            (now, config.source_name))
            self.db.execute("UPDATE queue SET status=CASE WHEN attempts>=? THEN 'dead_letter' ELSE 'retry' END, next_attempt=?,last_error='UNCERTAIN_DELIVERY',updated_at=? WHERE source=? AND status='inflight'",
                            (config.max_attempts, now, now, config.source_name))
            return True

    def renew(self, config, owner, now):
        result = self.db.execute("UPDATE sources SET lease_until=? WHERE name=? AND owner=? AND lease_until>?",
                                 (now + config.lease_seconds, config.source_name, owner, now))
        if result.rowcount != 1:
            raise RuntimeError("Source lease lost; stopping delivery")

    def release(self, source, owner):
        self.db.execute("UPDATE sources SET owner=NULL,lease_until=NULL WHERE name=? AND owner=?", (source, owner))

    def headers(self, source):
        row = self.db.execute("SELECT * FROM sources WHERE name=?", (source,)).fetchone()
        return {key: row[column] for key, column in [("If-None-Match", "etag"), ("If-Modified-Since", "last_modified")]
                if row and row[column] is not None}

    @staticmethod
    def key(payload):
        # Namespaces avoid a GUID colliding with a literal URL. Never use a date/content hash.
        return "id:" + payload.source_id if payload.source_id is not None else "url:" + payload.url

    def enqueue(self, source, items, now, *, config=None, owner=None):
        ids = {}
        with self.transaction():
            if config is not None:self.renew(config,owner,now)
            for item in items:
                if item.payload is None:
                    continue
                payload = item.payload.model_dump_json()
                key = self.key(item.payload)
                self.db.execute("INSERT INTO queue(source,item_key,payload,issues,status,next_attempt,created_at,updated_at) VALUES (?,?,?,?,'pending',?,?,?) ON CONFLICT(source,item_key) DO NOTHING",
                                (source, key, payload, json.dumps(item.issues), now, now, now))
                row = self.db.execute("SELECT * FROM queue WHERE source=? AND item_key=?", (source, key)).fetchone()
                if row['payload'] != payload:
                    issues = list(dict.fromkeys(json.loads(row['issues']) + ['LOCAL_PAYLOAD_CHANGED']))
                    self.db.execute("UPDATE queue SET issues=? WHERE id=?", (json.dumps(issues), row['id']))
                ids[item.index] = row['id']
        return ids

    def checkpoint(self, source, owner, scan, now):
        # Separate transaction AFTER durable enqueue. Crash here cannot discard the outbox.
        with self.transaction():
            row = self.db.execute("SELECT owner,lease_until FROM sources WHERE name=?", (source,)).fetchone()
            if row['owner'] != owner or row['lease_until'] <= now:
                raise RuntimeError("Source lease lost before checkpoint")
            self.db.execute("UPDATE sources SET last_success=?,last_error=NULL,fetch_failures=0,fetch_blocked=0,etag=CASE WHEN ?=304 THEN coalesce(?,etag) ELSE ? END,last_modified=CASE WHEN ?=304 THEN coalesce(?,last_modified) ELSE ? END WHERE name=?",
                            (now, scan.status, scan.etag, scan.etag, scan.status, scan.last_modified, scan.last_modified, source))

    def scan_error(self, source, owner, error):
        self.db.execute("UPDATE sources SET last_error=? WHERE name=? AND owner=?", (error, source, owner))

    def begin_fetch(self,config,owner,now,reset=False):
        with self.transaction():
            self.renew(config,owner,now)
            if reset:
                self.db.execute('UPDATE sources SET fetch_failures=0,fetch_blocked=0 WHERE name=?',(config.source_name,))
            row=self.db.execute('SELECT * FROM sources WHERE name=?',(config.source_name,)).fetchone()
            if row['fetch_blocked']:return 'blocked'
            if row['next_fetch']>now:return 'deferred'
            # Persist rate reservation before networking, even if the process dies.
            self.db.execute('UPDATE sources SET next_fetch=? WHERE name=?',(now+config.source_interval,config.source_name))
            return 'ready'

    def fetch_error(self,config,owner,error,now,random_value):
        with self.transaction():
            self.renew(config,owner,now)
            row=self.db.execute('SELECT * FROM sources WHERE name=?',(config.source_name,)).fetchone()
            failures=row['fetch_failures']+1
            blocked=not error.retryable or failures>=config.max_attempts
            delay=min(config.backoff_cap,config.backoff_base*2**min(failures-1,20))*(.5+.5*random_value)
            due=max(row['next_fetch'],now+delay,error.retry_at or now)
            self.db.execute('UPDATE sources SET fetch_failures=?,fetch_blocked=?,next_fetch=?,last_error=? WHERE name=?',
                (failures,int(blocked),due,error.code,config.source_name))

    def fetch_status(self,source):
        row=self.db.execute('SELECT fetch_failures,fetch_blocked,next_fetch,last_error FROM sources WHERE name=?',(source,)).fetchone()
        return dict(row)

    def rows(self, source):
        return self.db.execute("SELECT * FROM queue WHERE source=? ORDER BY id", (source,)).fetchall()

    def claim(self, config, owner, now, excluded):
        with self.transaction():
            self.renew(config, owner, now)
            rows = self.db.execute("SELECT * FROM queue WHERE source=? AND status IN ('pending','retry') AND next_attempt<=? ORDER BY next_attempt,id",
                                   (config.source_name, now)).fetchall()
            candidates = []
            for row in rows:
                if row['attempts'] >= config.max_attempts:
                    self.db.execute("UPDATE queue SET status='dead_letter',last_error='ATTEMPTS_EXHAUSTED' WHERE id=?", (row['id'],))
                elif row['id'] not in excluded:
                    candidates.append(row)
            row = candidates[0] if candidates else None
            if row is None:
                return None, 0
            rate = self.db.execute("SELECT next_request FROM rate_limits WHERE endpoint=?", (config.backend_url,)).fetchone()
            if rate and rate[0] > now:
                return None, rate[0] - now
            self.db.execute("INSERT INTO rate_limits VALUES (?,?) ON CONFLICT(endpoint) DO UPDATE SET next_request=excluded.next_request",
                            (config.backend_url, now + config.request_interval))
            self.db.execute("UPDATE queue SET status='inflight',attempts=attempts+1,updated_at=? WHERE id=?", (now, row['id']))
            self.db.execute("INSERT INTO attempts(queue_id,number,started_at,result) VALUES (?,?,?,'inflight')",
                            (row['id'], row['attempts'] + 1, now))
            return dict(row), 0

    def finish(self, config, owner, row, delivery, now, random_value):
        with self.transaction():
            self.renew(config, owner, now)
            attempt = row['attempts'] + 1
            if delivery.status in {'created', 'duplicate'}:
                status, due = 'delivered', now
            elif delivery.status in RETRYABLE:
                status = 'dead_letter' if attempt >= config.max_attempts else 'retry'
                delay = min(config.backoff_cap, config.backoff_base * 2 ** (attempt - 1))
                due = max(now + delay * (.5 + .5 * random_value), delivery.retry_at or now)
                if delivery.retry_at is not None:
                    self.db.execute("UPDATE rate_limits SET next_request=max(next_request,?) WHERE endpoint=?", (delivery.retry_at, config.backend_url))
            else:
                status, due = 'failed', now
            diag = json.dumps(delivery.diagnostics)
            self.db.execute("UPDATE queue SET status=?,next_attempt=?,news_id=?,diagnostics=?,http_status=?,last_error=?,updated_at=? WHERE id=? AND status='inflight'",
                            (status, due, delivery.news_id, diag, delivery.http_status,
                             None if status == 'delivered' else delivery.status, now, row['id']))
            self.db.execute("UPDATE attempts SET finished_at=?,result=?,http_status=?,diagnostics=? WHERE queue_id=? AND number=?",
                            (now, delivery.status, delivery.http_status, diag, row['id'], attempt))
