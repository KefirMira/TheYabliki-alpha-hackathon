import asyncio
import base64
from datetime import datetime, timezone
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError

from api.insights import get_insight_service
from main import app
from repositories.insight_repository import InsightRepository
from schemas.insights import InsightFeed
from services.company_profile_service import CompanyNotFound
from services.insight_cursor import InvalidInsightCursor, decode_cursor, encode_cursor
from services.insight_service import InsightNotFound, InsightService


STAMP = datetime(2026, 10, 22, 10, 20, 30, 123456, tzinfo=timezone.utc)
COMPANY = "SYNTH-COMPANY-A"


def feed_row(number):
    return dict(insight_id=number, run_id=number, type=None, relevance="high", summary="Synthetic summary",
                created_at=STAMP, status="COMPLETED")


def test_cursor_roundtrip_keeps_microseconds_and_company():
    token = encode_cursor(COMPANY, STAMP, 7)
    position = decode_cursor(token, COMPANY)
    assert position.created_at == STAMP and position.id == 7 and position.company_id == COMPANY
    assert decode_cursor(None, COMPANY) is None
    with pytest.raises(InvalidInsightCursor):
        decode_cursor(token, "SYNTH-COMPANY-B")


@pytest.mark.parametrize("payload", [
    {}, {"v": 2, "company_id": COMPANY, "created_at": STAMP.isoformat(), "id": 7},
    {"v": 1, "company_id": COMPANY, "created_at": "2026-10-22T10:20:30", "id": 7},
    {"v": 1, "company_id": COMPANY, "created_at": STAMP.isoformat(), "id": 0},
    {"v": 1, "company_id": COMPANY, "created_at": STAMP.isoformat(), "id": "7"},
    {"v": 1, "company_id": COMPANY, "created_at": STAMP.isoformat(), "id": True},
    {"v": 1, "company_id": COMPANY, "created_at": STAMP.isoformat(), "id": 2**63},
    {"v": 1, "company_id": COMPANY, "created_at": STAMP.isoformat(), "id": 7, "extra": 1},
])
def test_invalid_cursor_payload(payload):
    token = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    with pytest.raises(InvalidInsightCursor):
        decode_cursor(token, COMPANY)


@pytest.mark.parametrize("token", ["", "%%%", "a", "x" * 2049])
def test_invalid_cursor_encoding(token):
    with pytest.raises(InvalidInsightCursor):
        decode_cursor(token, COMPANY)


def test_service_limit_plus_one_and_last_visible_cursor():
    service = InsightService(Mock())
    service.companies.get_by_source_id = AsyncMock(return_value=SimpleNamespace(id=1))
    service.insights.list_completed = AsyncMock(return_value=[feed_row(3), feed_row(2), feed_row(1)])
    page = asyncio.run(service.list(COMPANY, 2))
    assert [item.insight_id for item in page.items] == [3, 2]
    assert decode_cursor(page.next_cursor, COMPANY).id == 2
    assert all(item.type is None for item in page.items)
    service.insights.list_completed.return_value = []
    empty = asyncio.run(service.list(COMPANY, 2))
    assert empty.items == [] and empty.next_cursor is None


def test_missing_company_and_foreign_card_do_not_read_evidence():
    service = InsightService(Mock())
    service.companies.get_by_source_id = AsyncMock(return_value=None)
    service.insights.get_completed = AsyncMock(return_value=None)
    service.insights.get_evidence = AsyncMock()
    with pytest.raises(CompanyNotFound):
        asyncio.run(service.card(COMPANY, 42))
    service.companies.get_by_source_id.return_value = SimpleNamespace(id=1)
    with pytest.raises(InsightNotFound):
        asyncio.run(service.card(COMPANY, 42))
    service.insights.get_evidence.assert_not_awaited()
    service.insights.get_completed.assert_awaited_once_with(1, 42)


def test_repository_uses_company_completed_filter_and_keyset_not_offset():
    session = Mock()
    result = Mock()
    result.mappings.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)
    repository = InsightRepository(session)
    position = decode_cursor(encode_cursor(COMPANY, STAMP, 7), COMPANY)
    asyncio.run(repository.list_completed(19, 2, position))
    compiled = session.execute.await_args.args[0].compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "COMPLETED" in compiled.params.values() and 19 in compiled.params.values()
    assert STAMP in compiled.params.values() and 7 in compiled.params.values()
    assert "ORDER BY" in sql and "created_at DESC" in sql and "id DESC" in sql
    assert "OFFSET" not in sql and 3 in compiled.params.values()


@pytest.fixture
def insight_api(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    service = SimpleNamespace(list=AsyncMock(return_value=InsightFeed(items=[])), card=AsyncMock())
    app.dependency_overrides[get_insight_service] = lambda: service
    yield service
    app.dependency_overrides.clear()


def test_empty_feed_contract(insight_api):
    with TestClient(app) as client:
        response = client.get(f"/api/companies/{COMPANY}/insights")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}
    insight_api.list.assert_awaited_once_with(COMPANY, 20, None)


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "limit=no", "cursor=%%%", "cursor=", "cursor=x"])
def test_invalid_feed_query_is_422(insight_api, query):
    with TestClient(app) as client:
        response = client.get(f"/api/companies/{COMPANY}/insights?{query}")
    assert response.status_code == 422
    insight_api.list.assert_not_awaited()


def test_cursor_from_other_company_is_422(insight_api):
    token = encode_cursor("SYNTH-COMPANY-B", STAMP, 7)
    with TestClient(app) as client:
        response = client.get(f"/api/companies/{COMPANY}/insights", params={"cursor": token})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_CURSOR"
    insight_api.list.assert_not_awaited()


@pytest.mark.parametrize("identifier", ["0", "-1", "not-an-id", str(2**63)])
def test_invalid_card_id_is_422(insight_api, identifier):
    with TestClient(app) as client:
        response = client.get(f"/api/companies/{COMPANY}/insights/{identifier}")
    assert response.status_code == 422
    insight_api.card.assert_not_awaited()


@pytest.mark.parametrize("route,method,error,status,code", [
    ("", "list", CompanyNotFound("missing"), 404, "COMPANY_NOT_FOUND"),
    ("/7", "card", CompanyNotFound("missing"), 404, "COMPANY_NOT_FOUND"),
    ("/7", "card", InsightNotFound(7), 404, "INSIGHT_NOT_FOUND"),
    ("", "list", SQLAlchemyError("private DSN"), 503, "DATABASE_UNAVAILABLE"),
    ("/7", "card", OSError("private DSN"), 503, "DATABASE_UNAVAILABLE"),
    ("/7", "card", TimeoutError("private DSN"), 503, "DATABASE_UNAVAILABLE"),
])
def test_read_errors_are_sanitized(insight_api, route, method, error, status, code):
    getattr(insight_api, method).side_effect = error
    with TestClient(app) as client:
        response = client.get(f"/api/companies/{COMPANY}/insights{route}")
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    assert "private DSN" not in response.text


def test_missing_database_returns_503_for_both_reads(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app) as client:
        for suffix in ("", "/7"):
            response = client.get(f"/api/companies/{COMPANY}/insights{suffix}")
            assert response.status_code == 503
            assert response.json()["detail"]["code"] == "DATABASE_UNAVAILABLE"
