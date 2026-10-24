
from pathlib import Path

from services.chunk_service import load_chunks
from settings import knowledge_base_dir


BASE_DIR = Path(__file__).resolve().parent.parent

PROCESSED_DIR = BASE_DIR / "data" / "processed"


def load_knowledge_base() -> list[dict]:
    """
    Загружает фрагменты из всех подготовленных
    JSON-документов в папке data/processed.
    """

    directory = knowledge_base_dir()
    if not directory.exists():
        return []

    all_chunks = []

    json_files = sorted(
        directory.glob("*.json")
    )

    for json_path in json_files:
        chunks = load_chunks(str(json_path))

        all_chunks.extend(chunks)

        print(
            f"Загружен документ: {json_path.name}, "
            f"фрагментов: {len(chunks)}"
        )

    return all_chunks
