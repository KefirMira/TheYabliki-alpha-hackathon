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
