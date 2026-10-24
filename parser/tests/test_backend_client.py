import httpx
import pytest

from parser.backend_client import BackendClient
from parser.collector import collect_once
from parser.config import Config
from parser.models import NewsPayload


def payload():
    return NewsPayload(title="Synthetic", content="Invented text", source_name="synthetic-demo", source_id="SYNTH-1")


@pytest.mark.parametrize("code,status", [(201, "created"), (200, "duplicate"), (409, "conflict"),
    (422, "invalid_data"), (503, "unavailable"), (403, "forbidden"), (500, "temporary_error"), (307, "http_error")])
def test_http_statuses_and_no_retry_or_redirect(code, status):
    calls = []
    def handler(request):
        calls.append(request)
        assert request.method == "POST" and request.url.path == "/api/news"
        return httpx.Response(code, json={"news_id": 17, "created": code == 201, "duplicate": code == 200,
                                         "diagnostics": ["CONTENT_MISMATCH"] if code == 200 else []},
                              headers={"Location": "https://example.invalid/must-not-follow"})
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        result = BackendClient(Config.from_env({}), http).deliver(payload())
    assert result.status == status and result.http_status == code and len(calls) == 1
    if code in {200, 201}:
        assert result.news_id == 17
    if code == 200:
        assert result.diagnostics == ["CONTENT_MISMATCH"]
    if code == 409:
        assert result.diagnostics == ["NEWS_IDENTITY_CONFLICT"]


@pytest.mark.parametrize("error,status", [(httpx.ReadTimeout, "timeout"), (httpx.ConnectError, "network_error")])
def test_network_failure_does_not_abort_other_items(error, status):
    calls = []
    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise error("synthetic failure", request=request)
        return httpx.Response(201, json={"news_id": len(calls), "created": True, "duplicate": False, "diagnostics": []})
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        report = collect_once(Config.from_env({}), BackendClient(Config.from_env({}), http))
    assert len(calls) == 5 and report["counts"][status] == 1 and report["counts"]["created"] == 4
    assert report["failed"]


@pytest.mark.parametrize("body", [
    {"news_id": False, "created": True, "duplicate": False, "diagnostics": []},
    {"news_id": -1, "created": True, "duplicate": False, "diagnostics": []},
    {"news_id": 1, "created": False, "duplicate": True, "diagnostics": []},
    {"news_id": 1, "created": True, "duplicate": False, "diagnostics": "not-a-list"},
    [], {},
])
def test_malformed_receipt_is_not_success(body):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(201, json=body))) as http:
        assert BackendClient(Config.from_env({}), http).deliver(payload()).status == "invalid_response"
