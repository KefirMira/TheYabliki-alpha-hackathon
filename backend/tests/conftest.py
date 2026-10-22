import os
import sys

import pytest


# These tests must neither load a developer's .env nor use a real LLM credential.
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
    os.environ.pop(key, None)


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)
    # An accidental import of the SDK fails instead of reaching a provider.
    monkeypatch.setitem(sys.modules, "openai", None)


@pytest.fixture
def test_database_url():
    url = os.environ.get("PROFILE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Run backend/tests/run-profile-tests.ps1 for synthetic PostgreSQL tests")
    return url


@pytest.fixture
def bundle_factory():
    from schemas.persisted_analysis import PersistableAnalysis

    def make(news="Synthetic persistence news", company_id="SYNTH-COMPANY-A"):
        fragments = [
            {"id": 1, "document": "synthetic-month.pdf", "page": 2, "chunk_id": 3,
             "date": "2026-08", "score": 0.42, "text": "Exact synthetic retrieval fragment.\nSecond line."},
            {"id": 2, "document": "synthetic-day.pdf", "page": 4, "chunk_id": 5,
             "date": "2026-08-12", "score": 0.31, "text": "Another exact synthetic fragment."},
        ]
        return PersistableAnalysis.model_validate({
            "analysis": {
                "company_id": company_id, "news": news, "relevance": "high", "summary": "Synthetic summary",
                "risks": ["Synthetic risk"], "opportunities": [], "recommendations": ["Synthetic action"],
                "sources": [{key: item[key] for key in ("id", "document", "page", "score")} for item in fragments],
                "validation": {"passed": False, "warnings": ["Synthetic warning"]},
            },
            "evidence": fragments, "model_name": "synthetic-model",
        })

    return make
