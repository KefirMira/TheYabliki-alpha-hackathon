"""Block credentials and SDK during collection as well as during test execution."""
import os
import sys

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
    os.environ.pop(key, None)
sys.modules["openai"] = None
