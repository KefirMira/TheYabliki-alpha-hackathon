"""Block credentials and SDK during collection as well as during test execution."""
import os
import sys
from pathlib import Path
import runpy
import pytest

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
    os.environ.pop(key, None)
sys.modules["openai"] = None

GUARD = Path(__file__).parent / 'offline'
runpy.run_path(str(GUARD / 'sitecustomize.py'))


@pytest.fixture(autouse=True)
def isolated_parser_state(monkeypatch, tmp_path):
    from parser.config import Config
    original = Config.from_env.__func__
    def configured(cls, env=None):
        values = dict(os.environ if env is None else env)
        values.setdefault('PARSER_STATE_PATH', str(tmp_path / 'state.sqlite3'))
        values.setdefault('PARSER_REQUEST_INTERVAL', '.001')
        return original(cls, values)
    monkeypatch.setattr(Config, 'from_env', classmethod(configured))
    monkeypatch.setenv('PARSER_STATE_PATH', str(tmp_path / 'state.sqlite3'))
    monkeypatch.setenv('PARSER_REQUEST_INTERVAL', '.001')
    # Child interpreters install the same guard before importing CLI or HTTP SDK.
    root = Path(__file__).resolve().parents[2]
    monkeypatch.setenv('PYTHONPATH', os.pathsep.join((str(GUARD), str(root))))
