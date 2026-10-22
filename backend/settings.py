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
