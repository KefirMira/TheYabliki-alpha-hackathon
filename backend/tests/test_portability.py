import json

import pytest
from fastapi.testclient import TestClient

from main import app
from settings import BASE_DIR, knowledge_base_dir, tesseract_command, tesseract_languages
from services.knowledge_base_service import load_knowledge_base
from api.readiness import rag_ready


def test_paths_and_ocr(monkeypatch, tmp_path):
    monkeypatch.delenv("RAG_KNOWLEDGE_BASE_DIR", raising=False)
    assert knowledge_base_dir() == BASE_DIR / "data/processed"
    monkeypatch.setenv("RAG_KNOWLEDGE_BASE_DIR", "private/prepared")
    assert knowledge_base_dir() == BASE_DIR / "private/prepared"
    monkeypatch.setenv("RAG_KNOWLEDGE_BASE_DIR", str(tmp_path))
    assert knowledge_base_dir() == tmp_path
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.delenv("TESSERACT_LANGUAGES", raising=False)
    assert tesseract_command() == "tesseract"
    assert tesseract_languages() == "rus+eng"
    monkeypatch.setenv("TESSERACT_CMD", "/opt/ocr/tesseract")
    monkeypatch.setenv("TESSERACT_LANGUAGES", "eng")
    assert tesseract_command() == "/opt/ocr/tesseract"
    assert tesseract_languages() == "eng"


@pytest.mark.parametrize("case", ["missing", "empty", "invalid", "no_text", "valid"])
def test_knowledge_readiness(monkeypatch, tmp_path, case):
    directory = tmp_path / "kb"
    monkeypatch.setenv("RAG_KNOWLEDGE_BASE_DIR", str(directory))
    if case != "missing":
        directory.mkdir()
    if case in ("no_text", "valid"):
        (directory / "synthetic.json").write_text(json.dumps({
            "document": "synthetic.pdf", "pages": [{"page": 1,
            "text": "Synthetic evidence" if case == "valid" else ""}]}), encoding="utf-8")
    if case == "invalid":
        (directory / "broken.json").write_text("{", encoding="utf-8")
    assert rag_ready() is (case == "valid")
    if case == "missing":
        assert load_knowledge_base() == []


def test_liveness_unchanged_readiness_sanitized(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("RAG_KNOWLEDGE_BASE_DIR", str(tmp_path / "missing"))
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "checks": {
        "rag": False, "llm_config": False, "database": False}}
    assert str(tmp_path) not in response.text


def test_requirements_utf8():
    contents = (BASE_DIR / "requirements.txt").read_bytes()
    assert not contents.startswith(b"\xff\xfe")
    assert "-r requirements-db.txt" in contents.decode("utf-8")


@pytest.mark.parametrize("database_state", ["ready", "missing_table", "unavailable"])
def test_readiness_database(monkeypatch, tmp_path, database_state):
    from api.readiness import TABLES

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("RAG_KNOWLEDGE_BASE_DIR", str(tmp_path))
    (tmp_path / "synthetic.json").write_text(json.dumps({
        "document": "synthetic.pdf", "pages": [{"page": 1, "text": "Synthetic"}]}), encoding="utf-8")
    for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.setenv(key, "synthetic-config-only")
    seen = []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute(self, statement, params):
            seen.append(params["name"])
            if database_state == "unavailable":
                raise OSError("secret DSN must not appear")

            class Result:
                def scalar_one(self):
                    return None if database_state == "missing_table" else "existing"

            return Result()

    with TestClient(app) as client:
        app.state.company_sessions = Session
        response = client.get("/ready")
    assert response.status_code == (200 if database_state == "ready" else 503)
    assert response.json()["checks"] == {
        "rag": True, "llm_config": True, "database": database_state == "ready"}
    assert "secret" not in response.text
    if database_state == "ready":
        assert seen == [f"public.{table}" for table in TABLES]
