import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from main import app
from settings import execution_mode

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("path", ["/api/analyze", "/api/analyze-rag", "/api/analyze-company",
                                  "/api/companies/DEMO-001/news/1/analyses",
                                  "/api/companies/DEMO-001/analyses"])
def test_demo_blocks_ai_before_body_or_database(monkeypatch, path):
    monkeypatch.setenv("AI_MODE", "demo")
    monkeypatch.setenv("LLM_API_KEY", "synthetic-key-must-not-be-used")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app) as client:
        response = client.post(path, json={})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "AI_DISABLED_IN_DEMO"


def test_invalid_mode_fails_closed(monkeypatch):
    monkeypatch.setenv("AI_MODE", "typo")
    with pytest.raises(ValueError, match="AI_MODE"):
        execution_mode()


@pytest.mark.parametrize("database_ready", [True, False])
def test_demo_readiness_requires_database_only(monkeypatch, database_ready):
    monkeypatch.setenv("AI_MODE", "demo")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr("api.readiness.rag_ready", lambda: False)

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute(self, *args):
            class Result:
                def scalar_one(self):
                    return True if database_ready else None
            return Result()

    with TestClient(app) as client:
        app.state.company_sessions = Session
        response = client.get("/ready")
    assert response.status_code == (200 if database_ready else 503)
    assert response.json()["checks"] == {"database": database_ready, "rag": False, "llm_config": False}


@pytest.mark.parametrize("full", [False, True])
def test_compose_resolved_configuration(full):
    if not shutil.which("docker"):
        pytest.skip("Docker CLI is required only to validate the resolved Compose configuration")
    env = {**os.environ, "CORS_ORIGINS": "http://localhost:5173",
           "LLM_API_KEY": "synthetic-unused", "LLM_BASE_URL": "https://example.invalid",
           "LLM_MODEL": "synthetic", "RAG_CORPUS_DIR": str(ROOT)}
    command = ["docker", "compose", "-p", "pulse-config-only", "-f", str(ROOT / "compose.frontend.yml")]
    if full:
        command += ["-f", str(ROOT / "compose.frontend.full.yml")]
    config = json.loads(subprocess.check_output(command + ["config", "--format", "json"], env=env))
    backend = config["services"]["backend"]
    db = config["services"]["postgres"]
    assert "ports" not in db  # No host access or connection to a production database.
    assert backend["environment"]["DATABASE_URL"].endswith("@postgres:5432/pulse_demo")
    assert backend["ports"][0]["host_ip"] == "127.0.0.1"
    assert backend["environment"]["AI_MODE"] == ("full" if full else "demo")
    assert backend["environment"]["LLM_API_KEY"] == ("synthetic-unused" if full else "")
    assert backend["environment"]["CORS_ORIGINS"] == "http://localhost:5173"
    assert backend["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert backend["healthcheck"]
    assert len(backend["volumes"]) == 1 and backend["volumes"][0]["read_only"]
    if full:
        assert backend["volumes"][0]["type"] == "bind"
        # Compose drops explicit false values from normalized JSON.
        assert not backend["volumes"][0].get("bind", {}).get("create_host_path", False)
    init = [v for v in db["volumes"] if v["target"].startswith("/docker-entrypoint-initdb.d/")]
    assert len(init) == 8 and all(v["read_only"] for v in init)
    assert sorted(Path(v["source"]).name for v in init) == [
        "002_pulse_features.sql", "003_integrity.sql", "004_news_external_identity.sql", "005_saved_news_analysis_jobs.sql", "006_news_company_matching.sql", "007_auth_access.sql", "frontend-demo.sql", "schema.sql"]
    assert sorted(Path(v["target"]).name for v in init) == [
        "001_schema.sql", "002_pulse_features.sql", "003_integrity.sql",
        "004_news_external_identity.sql", "005_saved_news_analysis_jobs.sql", "006_news_company_matching.sql", "007_auth_access.sql", "900_demo.sql"]


def test_docker_context_is_allowlisted():
    ignore = (ROOT / "backend/.dockerignore").read_text()
    assert ignore.startswith("**\n")
    assert "!data" not in ignore and "!.env" not in ignore
    dockerfile = (ROOT / "backend/Dockerfile").read_text()
    assert "COPY . " not in dockerfile and "USER backend" in dockerfile
    assert "FROM python:3.12" in dockerfile


def test_migration_tests_use_selected_database_root(monkeypatch, tmp_path):
    import runpy

    migrations = tmp_path / "migrations"
    migrations.mkdir()
    marker = "-- synthetic selected migration; never executed\n"
    (migrations / "004_news_external_identity.sql").write_text(marker, encoding="utf-8")
    monkeypatch.setenv("NEWS_IDENTITY_DATABASE_ROOT", str(tmp_path))
    selected = runpy.run_path(str(ROOT / "backend/tests/test_news_identity_migration.py"))
    assert selected["DATABASE_ROOT"] == tmp_path.resolve()
    assert selected["MIGRATION"] == marker
