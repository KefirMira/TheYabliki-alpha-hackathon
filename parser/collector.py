from collections import Counter
import json
import os
from pathlib import Path
import tempfile

from .backend_client import BackendClient
from .rss import read_rss


def collect_once(config, backend=None):
    items = read_rss(config.rss_path, config.source_name)
    backend = backend or BackendClient(config)
    results = []
    try:
        for item in items:
            result = {"item": item.index, "source_id": item.payload.source_id if item.payload else None,
                      "issues": item.issues}
            result.update(backend.deliver(item.payload).to_dict() if item.payload else {"status": "skipped"})
            results.append(result)
    finally:
        backend.close()
    counts = dict(Counter(item["status"] for item in results))
    failed = any(item["status"] not in {"created", "duplicate", "skipped"} for item in results)
    return {"source_name": config.source_name, "counts": counts, "items": results, "failed": failed}


def save_report(path: Path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".rss-report-", suffix=".tmp", delete=False) as file:
            temporary = Path(file.name)
            json.dump(report, file, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
