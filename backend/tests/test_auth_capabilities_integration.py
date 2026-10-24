"""Actual auth and PostgreSQL ACL; no automatic legacy auth overrides."""
import asyncio
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.company_analyses import get_analysis_analyzer
from main import app
from test_auth_integration import auth_database, headers
from test_news_identity_migration import identity_dsn

pytestmark = pytest.mark.integration
PATH = "/api/companies/SYNTH-A/capabilities"


@pytest.mark.parametrize("mode", ["demo", "full"])
@pytest.mark.parametrize("can_write", [False, True])
def test_capabilities_readonly_with_real_permissions(identity_dsn, monkeypatch, mode, can_write):
    async def scenario():
        async with auth_database(identity_dsn, monkeypatch) as (c, ids):
            monkeypatch.setenv("AI_MODE", mode)
            await c.execute("UPDATE auth_user_companies SET can_analyze=$2 WHERE user_id=$1", ids["alice"], can_write)
            with TestClient(app) as client:
                a = headers(client, "alice")
                sessions = app.state.company_sessions
                @asynccontextmanager
                async def readonly():
                    async with sessions() as s:
                        await s.execute(text("SET TRANSACTION READ ONLY"))
                        yield s
                app.state.company_sessions = readonly
                response = client.get(PATH + "?can_analyze=true&company_id=SYNTH-B", headers=a)
                assert response.status_code == 200, response.text
                assert response.headers["Cache-Control"] == "no-store"
                body = response.json()
                assert body["company_id"] == "SYNTH-A" and body["mode"] == mode
                assert body["external_provider"]["state"] == "UNKNOWN"
                assert body["operations"]["analyze_new"]["state"] == "BLOCKED"
                assert body["operations"]["reuse_completed"]["state"] == ("UNKNOWN" if mode == "full" and can_write else "BLOCKED")
                denied = client.get(PATH.replace("SYNTH-A", "SYNTH-B") + "?source_id=SYNTH-A", headers=a)
                absent = client.get(PATH.replace("SYNTH-A", "UNKNOWN-COMPANY"), headers=a)
                assert denied.status_code == absent.status_code == 403
                assert denied.json() == absent.json()
                app.state.company_sessions = sessions
                # Advice never confers an execution right.
                if not can_write:
                    assert client.post("/api/companies/SYNTH-A/analyses", headers=a, json={"news": {"text": "Synthetic"}}).status_code == 403
            for table in ("news_articles", "news_analysis_jobs", "news_analysis_attempts", "analysis_runs", "company_news_analyses", "insight_evidence"):
                assert await c.fetchval("SELECT count(*) FROM " + table) == 0
    asyncio.run(scenario())


@pytest.mark.parametrize("change", ["expired", "revoked", "disabled", "membership"])
def test_capabilities_rechecks_session_and_membership(identity_dsn, monkeypatch, change):
    async def scenario():
        async with auth_database(identity_dsn, monkeypatch) as (c, ids):
            with TestClient(app) as client:
                a = headers(client, "alice")
                assert client.get(PATH, headers=a).status_code == 200
                if change == "expired":
                    await c.execute("UPDATE auth_sessions SET created_at=now()-interval '2 hours',expires_at=now()-interval '1 hour'")
                elif change == "revoked":
                    await c.execute("UPDATE auth_sessions SET revoked_at=clock_timestamp()")
                elif change == "disabled":
                    await c.execute("UPDATE auth_users SET is_active=false WHERE id=$1", ids["alice"])
                else:
                    await c.execute("DELETE FROM auth_user_companies WHERE user_id=$1", ids["alice"])
                assert client.get(PATH, headers=a).status_code == (403 if change == "membership" else 401)
    asyncio.run(scenario())


def test_capabilities_do_not_disclose_or_mutate_job_states(identity_dsn, monkeypatch, bundle_factory):
    async def scenario():
        async with auth_database(identity_dsn, monkeypatch) as (c, _):
            calls = []
            async def fake(**kwargs):
                calls.append(1)
                return bundle_factory(news=kwargs["news"], company_id=kwargs["company"].company_id)
            app.dependency_overrides[get_analysis_analyzer] = lambda: fake
            try:
                with TestClient(app) as client:
                    a, b = headers(client, "alice"), headers(client, "bob")
                    news = client.post("/api/news", headers=a, json={"title": "Synthetic", "content": "Synthetic news"}).json()["news_id"]
                    saved_path = f"/api/companies/SYNTH-A/news/{news}/analyses"
                    assert client.post(saved_path, headers=a).status_code == 201
                    expected = client.get(PATH, headers=b).json()
                    for state in ("COMPLETED", "RUNNING", "FAILED"):
                        # Synthetic fixture changes status, never authorizes or retries a call.
                        await c.execute("UPDATE analysis_runs SET status=$1", state)
                        before = await c.fetchval("SELECT jsonb_agg(to_jsonb(x))::text FROM news_analysis_attempts x")
                        assert client.get(PATH, headers=b).json() == expected
                        assert await c.fetchval("SELECT jsonb_agg(to_jsonb(x))::text FROM news_analysis_attempts x") == before
                        assert client.post(saved_path, headers=b).status_code == 403
                        assert calls == [1]
                    await c.execute("UPDATE analysis_runs SET status='COMPLETED'")
                    assert client.post(saved_path, headers=a).status_code == 200 and calls == [1]
                    assert client.get("/api/companies/SYNTH-A/insights", headers=b).json()["items"] == []
                    assert await c.fetchval("SELECT count(*) FROM news_analysis_attempts") == 1
            finally:
                app.dependency_overrides.pop(get_analysis_analyzer, None)
    asyncio.run(scenario())
