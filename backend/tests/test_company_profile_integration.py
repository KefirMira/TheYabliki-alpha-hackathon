import asyncio
from decimal import Decimal
import socket

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from main import app


pytestmark = pytest.mark.integration


def test_real_postgres_profile_and_not_found(monkeypatch, test_database_url):
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    with TestClient(app) as client:
        response = client.get("/api/companies/SYNTH-COMPANY-A")
        assert response.status_code == 200
        assert response.json() == {
            "company_id": "SYNTH-COMPANY-A",
            "name": "Synthetic Workshop A",
            "name_is_placeholder": False,
            "industry": "Synthetic manufacturing",
            "region": "Test region A",
            "revenue": "1000.25",
            "revenue_year": None,
            "client_status": "CLIENT",
            "credit_exposure": None,
        }
        assert client.get("/api/companies/not-present").status_code == 404
        # SQL-like input must remain a literal source_id, never a query fragment.
        assert client.get("/api/companies/synthetic' OR true --").status_code == 404
        assert client.get("/api/companies/SYNTH-COMPANY-B").json()["revenue"] == "2000.50"
    assert app.state.company_sessions is None


def test_real_postgres_decimal_placeholder_and_null(monkeypatch, test_database_url):
    async def insert_fixture():
        engine = create_async_engine(test_database_url)
        try:
            async with engine.begin() as connection:
                await connection.execute(text(
                    "INSERT INTO public.companies(source_id,name,revenue) "
                    "VALUES (:source_id,:source_id,:revenue)"
                ), {"source_id": "SYNTH-EXACT-DECIMAL", "revenue": Decimal("9999999999999999.99")})
                await connection.execute(text(
                    "INSERT INTO public.companies(source_id,name) VALUES ('SYNTH-NULLS','Synthetic Null Profile')"
                ))
        finally:
            await engine.dispose()

    async def delete_fixture():
        engine = create_async_engine(test_database_url)
        try:
            async with engine.begin() as connection:
                await connection.execute(text(
                    "DELETE FROM public.companies WHERE source_id IN ('SYNTH-EXACT-DECIMAL','SYNTH-NULLS')"
                ))
        finally:
            await engine.dispose()

    asyncio.run(insert_fixture())
    try:
        monkeypatch.setenv("DATABASE_URL", test_database_url)
        with TestClient(app) as client:
            data = client.get("/api/companies/SYNTH-EXACT-DECIMAL").json()
            assert data["revenue"] == "9999999999999999.99"
            assert data["name"] is None
            assert data["name_is_placeholder"] is True
            assert data["credit_exposure"] is None
            nulls = client.get("/api/companies/SYNTH-NULLS").json()
            assert nulls["revenue"] is None
            assert nulls["industry"] is None
            assert nulls["credit_exposure"] is None
    finally:
        asyncio.run(delete_fixture())


def test_connection_refused_returns_503(monkeypatch):
    # Reserving a non-listening port prevents accidentally contacting another DB.
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
        monkeypatch.setenv("DATABASE_URL", f"postgresql+asyncpg://test:test@127.0.0.1:{port}/no_database")
        with TestClient(app) as client:
            response = client.get("/api/companies/SYNTH-COMPANY-A")
            assert response.status_code == 503
            assert response.json()["detail"]["code"] == "DATABASE_UNAVAILABLE"
            assert "no_database" not in response.text
