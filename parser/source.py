"""Conditional-fetch interface; this version implements local files ONLY."""
from dataclasses import dataclass, field

from .rss import Item, read_rss


@dataclass
class Scan:
    status: int = 200
    items: list[Item] = field(default_factory=list)
    etag: str | None = None
    last_modified: str | None = None


def fetch_local(config, conditional_headers):
    # Validators are reserved for a future HTTP adapter; no HTTP RSS requests.
    return Scan(items=read_rss(config.rss_path, config.source_name))
