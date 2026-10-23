from collections import Counter
import json
import os
from pathlib import Path
import tempfile
import random
import time
from threading import Event
from uuid import uuid4
from xml.etree.ElementTree import ParseError

from .backend_client import BackendClient
from .models import NewsPayload
from .source import fetch_local
from .http_source import HTTPRSS, SourceError
from .state import State


def collect_once(config, backend=None, *, clock=time.time, stop=None, wait=None,
                 random_value=random.random, fetch=None, after_enqueue=None, reset_source=False):
    stop = stop if stop is not None else Event()
    wait = wait or stop.wait
    state = State(config.state_path)
    owner = uuid4().hex
    backend = backend or BackendClient(config, clock=clock)
    results, deliveries, source_error = [], {}, None
    acquired = False
    fetch=fetch or (HTTPRSS() if config.source_mode=='http' else fetch_local)
    source_status='ready'
    try:
        acquired = state.acquire(config, owner, clock())
        if not acquired:
            return {"source_name": config.source_name, "counts": {"source_busy": 1},
                    "items": [], "failed": False, "source_busy": True}
        items = []
        try:
            if config.source_mode=='http':source_status=state.begin_fetch(config,owner,clock(),reset_source)
            if source_status=='ready':
                scan = fetch(config, state.headers(config.source_name))
                if scan.status not in {200, 304} or (scan.status == 304 and scan.items):
                    raise ValueError("Invalid source response")
                items = scan.items
                state.enqueue(config.source_name, items, clock(),config=config,owner=owner)
                if after_enqueue is not None:
                    after_enqueue()  # Outbox committed; checkpoint deliberately not yet advanced.
                state.checkpoint(config.source_name, owner, scan, clock())
            elif source_status=='blocked':source_error='RSS_SOURCE_BLOCKED'
        except SourceError as error:
            source_error=error.code
            state.fetch_error(config,owner,error,clock(),random_value())
        except (OSError, ValueError, ParseError) as error:
            source_error = type(error).__name__
            state.scan_error(config.source_name, owner, source_error)
        attempted = set()
        while not stop.is_set():
            row, delay = state.claim(config, owner, clock(), attempted)
            if row is None:
                # Never wait for retry deadlines in --once. Short rate-limit spacing
                # is interruptible; a server Retry-After persists until a later run.
                if delay and delay <= config.request_interval + .001:
                    if wait(delay):
                        break
                    continue
                break
            attempted.add(row['id'])
            delivery = backend.deliver(NewsPayload.model_validate_json(row['payload']))
            state.finish(config, owner, row, delivery, clock(), random_value())
            deliveries[row['id']] = delivery.to_dict()
        rows = {row['id']: row for row in state.rows(config.source_name)}
        for item in items:
            if item.payload is None:
                results.append({"item": item.index, "issues": item.issues, "status": "skipped"})
        # One result per durable identity, including items absent in the current RSS / 304.
        for row in rows.values():
            payload = NewsPayload.model_validate_json(row['payload'])
            result = {"queue_id": row['id'], "source_id": payload.source_id, "issues": json.loads(row['issues']),
                      "status": "already_delivered" if row['status'] == 'delivered' else row['status'],
                      "queue_status": row['status'], "attempts": row['attempts'], "next_attempt_at": row['next_attempt'],
                      "news_id": row['news_id'], "diagnostics": json.loads(row['diagnostics']), "http_status": row['http_status']}
            result.update(deliveries.get(row['id'], {}))
            results.append(result)
        failed = source_error is not None or any(row['status'] != 'delivered' for row in rows.values())
        return {"source_name": config.source_name, "counts": dict(Counter(item['status'] for item in results)),
                "items": results, "failed": failed, "source_error": source_error,
                "source_fetch_status":source_status,"source_fetch":state.fetch_status(config.source_name),
                "queue_counts": dict(Counter(row['status'] for row in rows.values()))}
    finally:
        if acquired:
            state.release(config.source_name, owner)
        state.close()
        backend.close()


def poll(config, stop, on_report, *, collect=collect_once):
    while not stop.is_set():
        on_report(collect(config, stop=stop))
        if stop.wait(config.poll_interval):
            break


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
