"""Process environment only: never read backend/.env or inherit backend settings."""
from dataclasses import dataclass
import os
import math
from pathlib import Path
import re
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, TypeAdapter

PARSER_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Config:
    rss_path: Path
    report_path: Path
    backend_url: str
    source_name: str
    timeout: float
    state_path: Path
    max_attempts: int
    backoff_base: float
    backoff_cap: float
    poll_interval: float
    request_interval: float
    lease_seconds: float
    source_mode: str = 'local'
    rss_url: str | None = None
    http_enabled: bool = False
    source_interval: float = 300
    max_response_bytes: int = 1_048_576
    max_redirects: int = 3

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        def path(key, default):
            raw = env.get(key, default)
            if "://" in raw:
                raise ValueError(f"{key}: only a local file path is allowed")
            value = Path(raw).expanduser()
            return (value if value.is_absolute() else PARSER_DIR / value).resolve()
        rss = path("PARSER_RSS_PATH", "fixtures/synthetic.xml")
        report = path("PARSER_REPORT_PATH", "reports/last-run.json")
        if report.suffix.lower() != ".json" or report == rss:
            raise ValueError("PARSER_REPORT_PATH must be a separate JSON file")
        base = env.get("PARSER_BACKEND_URL", "http://127.0.0.1:8000")
        TypeAdapter(AnyHttpUrl).validate_python(base)
        parts = urlsplit(base)
        if (parts.scheme not in {"http", "https"} or parts.hostname not in {"localhost", "127.0.0.1", "::1"}
                or parts.username is not None or parts.password is not None
                or parts.path not in {"", "/"} or parts.query or parts.fragment
                or any(ord(c) <= 32 or ord(c) == 127 for c in base) or "\\" in base):
            raise ValueError("PARSER_BACKEND_URL must be a loopback HTTP/HTTPS origin without credentials")
        source = env.get("PARSER_SOURCE_NAME", "synthetic-demo")
        if len(source) > 100 or re.fullmatch(r"[a-z0-9._-]+", source) is None:
            raise ValueError("PARSER_SOURCE_NAME must be lowercase ASCII [a-z0-9._-], 1..100 characters")
        timeout = float(env.get("PARSER_HTTP_TIMEOUT", "10"))
        if not 0 < timeout <= 60:
            raise ValueError("PARSER_HTTP_TIMEOUT must be in (0, 60]")
        state = path("PARSER_STATE_PATH", "state/parser.sqlite3")
        if state in {rss, report} or state.suffix.lower() not in {".sqlite3", ".sqlite", ".db"}:
            raise ValueError("PARSER_STATE_PATH must be a separate SQLite file")
        def number(key, default, minimum, maximum):
            value = float(env.get(key, str(default)))
            if not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError(f"{key} must be in [{minimum}, {maximum}]")
            return value
        attempts = int(env.get("PARSER_MAX_ATTEMPTS", "5"))
        if not 1 <= attempts <= 20:
            raise ValueError("PARSER_MAX_ATTEMPTS must be in [1, 20]")
        delay = number("PARSER_BACKOFF_BASE", 2, .01, 3600)
        cap = number("PARSER_BACKOFF_CAP", 300, delay, 86400)
        poll = number("PARSER_POLL_INTERVAL", 30, .01, 86400)
        interval = number("PARSER_REQUEST_INTERVAL", .2, .001, 60)
        lease = number("PARSER_LEASE_SECONDS", 180, timeout + interval + 10, 86400)
        mode=env.get('PARSER_SOURCE_MODE','local')
        if mode not in {'local','http'}:raise ValueError('PARSER_SOURCE_MODE must be local or http')
        enabled=env.get('PARSER_HTTP_RSS_ENABLED','0')
        if enabled not in {'0','1'}:raise ValueError('PARSER_HTTP_RSS_ENABLED must be 0 or 1')
        url=env.get('PARSER_RSS_URL') or None
        if mode=='http':
            if enabled!='1' or not url or not env.get('PARSER_SOURCE_NAME'):
                raise ValueError('HTTP RSS requires explicit enable, URL and stable source_name')
            from .http_source import parse_url
            parse_url(url)  # Syntax only; no DNS or request during configuration.
        source_interval=number('PARSER_SOURCE_INTERVAL',300,1,86400)
        size=int(env.get('PARSER_RSS_MAX_BYTES','1048576'))
        redirects=int(env.get('PARSER_RSS_MAX_REDIRECTS','3'))
        if not 1<=size<=1048576 or not 0<=redirects<=5:
            raise ValueError('RSS size must be 1..1048576; redirects 0..5')
        return cls(rss, report, base.rstrip("/"), source, timeout, state,
                   attempts, delay, cap, poll, interval, lease,mode,url,enabled=='1',source_interval,size,redirects)
