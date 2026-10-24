"""Local substitute HTTP backend only; no FastAPI, database or LLM service."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Lock, Thread

import pytest

from parser.__main__ import main
from parser.collector import collect_once, save_report
from parser.config import Config


@contextmanager
def stub_backend(first_status=None):
    records = {}
    requests = []
    lock = Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            incoming = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert self.path == "/api/news"  # Any AI endpoint is a test failure.
            with lock:
                requests.append(incoming)
                if first_status is not None and len(requests) == 1:
                    status, response = first_status, {"detail": {"code": "synthetic-test-error"}}
                else:
                    key = (incoming["source_name"], incoming["source_id"]) if incoming["source_id"] else incoming["url"]
                    exists = key in records
                    if not exists:
                        records[key] = {"id": len(records) + 1, "content": incoming["content"]}
                    stored = records[key]
                    status = 200 if exists else 201
                    response = {"news_id": stored["id"], "created": not exists, "duplicate": exists,
                                "diagnostics": ["CONTENT_MISMATCH"] if incoming["content"] != stored["content"] else []}
            encoded = json.dumps(response).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests, records
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_real_http_repeat_delivery_and_receipt_report(tmp_path):
    with stub_backend() as (url, requests, records):
        config = Config.from_env({"PARSER_BACKEND_URL": url})
        first = collect_once(config)
        second = collect_once(config)
        assert first["counts"] == {"created": 5, "skipped": 5}
        assert second["counts"] == {"already_delivered": 5, "skipped": 5}
        assert len(requests) == 5 and len(records) == 5
        assert [item.get("news_id") for item in first["items"]] == [item.get("news_id") for item in second["items"]]
        assert requests[0]["published_at"] == "2026-01-01T09:00:00Z"
        assert requests[2]["published_at"] is None
        assert all(p["source_name"] == "synthetic-demo" for p in requests)
        output = tmp_path / "report.json"
        save_report(output, second)
        assert json.loads(output.read_text(encoding="utf-8")) == second
        assert "content" not in second["items"][0] and not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("code,status", [(409, "conflict"), (422, "invalid_data"), (503, "unavailable")])
def test_http_failure_does_not_stop_the_run(code, status):
    with stub_backend(code) as (url, requests, _):
        report = collect_once(Config.from_env({"PARSER_BACKEND_URL": url}))
    assert len(requests) == 5 and report["counts"] == {status: 1, "created": 4, "skipped": 5}
    assert report["failed"] and next(item for item in report['items'] if item.get('queue_id'))["http_status"] == code


def test_changed_text_duplicate_is_recorded(tmp_path):
    with stub_backend() as (url, _, records):
        config = Config.from_env({"PARSER_BACKEND_URL": url})
        collect_once(config)
        changed = tmp_path / "changed.xml"
        changed.write_text(config.rss_path.read_text().replace("workshop</strong>", "modified workshop</strong>"), encoding="utf-8")
        report = collect_once(Config.from_env({"PARSER_BACKEND_URL": url, "PARSER_RSS_PATH": str(changed)}))
    assert 'LOCAL_PAYLOAD_CHANGED' in next(item for item in report['items'] if item.get('queue_id'))['issues']
    assert len(records) == 5


def test_real_http_backend_recovers_and_queue_restarts():
    from parser.tests.test_state_delivery import Clock
    clock = Clock()
    with stub_backend(503) as (url, requests, records):
        config = Config.from_env({'PARSER_BACKEND_URL': url})
        first = collect_once(config, clock=clock, wait=clock.wait)
        assert first['queue_counts'] == {'retry': 1, 'delivered': 4}
        clock.now += 100
        recovered = collect_once(config, clock=clock, wait=clock.wait)
        assert recovered['queue_counts'] == {'delivered': 5}
        assert len(requests) == 6 and len(records) == 5


@pytest.mark.parametrize("first_status,exit_code", [(None, 0), (503, 1)])
def test_cli_once_writes_receipts(monkeypatch, tmp_path, capsys, first_status, exit_code):
    with stub_backend(first_status) as (url, _, _):
        monkeypatch.setenv("PARSER_BACKEND_URL", url)
        monkeypatch.setenv("PARSER_REPORT_PATH", str(tmp_path / "report.json"))
        assert main(["--once"]) == exit_code
    printed = json.loads(capsys.readouterr().out)
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8")) == printed
    assert any(item.get("news_id") for item in printed["items"])


def test_cli_invalid_input_is_sanitized(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("PARSER_RSS_PATH", str(tmp_path / "missing.xml"))
    monkeypatch.setenv("PARSER_REPORT_PATH", str(tmp_path / "report.json"))
    assert main(["--once"]) == 2
    assert json.loads(capsys.readouterr().err)["error_type"] == "FileNotFoundError"
    assert json.loads((tmp_path / 'report.json').read_text())['source_error'] == 'FileNotFoundError'


def test_cli_requires_exactly_one_mode():
    with pytest.raises(SystemExit) as error:
        main(["--poll", "--once"])
    assert error.value.code == 2


def test_python_module_cli_with_local_backend(tmp_path):
    root = Path(__file__).resolve().parents[2]
    with stub_backend() as (url, requests, _):
        env = {**os.environ, "PARSER_BACKEND_URL": url, "PARSER_SOURCE_NAME": "synthetic-demo",
               "PARSER_RSS_PATH": str(root / "parser/fixtures/synthetic.xml"),
               "PARSER_REPORT_PATH": str(tmp_path / "module-report.json"), "PARSER_HTTP_TIMEOUT": "5"}
        result = subprocess.run([sys.executable, "-m", "parser", "--once"], cwd=root, env=env,
                                capture_output=True, text=True, encoding="utf-8", timeout=20)
        restarted = subprocess.run([sys.executable, "-m", "parser", "--once"], cwd=root, env=env,
                                   capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["counts"] == {"created": 5, "skipped": 5}
    assert len(requests) == 5 and all("content" in payload for payload in requests)
    assert restarted.returncode == 0, restarted.stderr
    assert json.loads(restarted.stdout)['counts'] == {'already_delivered': 5, 'skipped': 5}
