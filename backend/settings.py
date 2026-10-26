"""Portable paths; relative configuration paths are anchored to backend/."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def knowledge_base_dir() -> Path:
    path = Path(os.environ.get("RAG_KNOWLEDGE_BASE_DIR") or "data/processed").expanduser()
    return path if path.is_absolute() else BASE_DIR / path


def tesseract_command() -> str:
    return os.environ.get("TESSERACT_CMD") or "tesseract"


def tesseract_languages() -> str:
    return os.environ.get("TESSERACT_LANGUAGES") or "rus+eng"


def execution_mode() -> str:
    mode = os.environ.get("AI_MODE", "full")
    if mode not in {"demo", "full"}:
        raise ValueError("AI_MODE must be demo or full")
    return mode


def ai_disabled_reason() -> str | None:
    """Shared mode policy for execution and read-only capability reporting."""
    return "AI_DISABLED_IN_DEMO" if execution_mode() == "demo" else None


def saved_pilot_offline() -> bool:
    """Dedicated offline diagnostics; never enables AI or changes other modes."""
    return os.environ.get('SAVED_PILOT_OFFLINE') == '1' and execution_mode() == 'demo'
