"""Process environment only: never read backend/.env or inherit backend settings."""
from dataclasses import dataclass
import os
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
        return cls(rss, report, base.rstrip("/"), source, timeout)
