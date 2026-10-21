
import json
from pathlib import Path


def load_chunks(
    json_path: str,
    chunk_size: int = 1000,
    overlap: int = 200
) -> list[dict]:

    if chunk_size <= 0 or not 0 <= overlap < chunk_size:
        raise ValueError("Некорректные параметры разбиения")

    with Path(json_path).open("r", encoding="utf-8") as file:
        document = json.load(file)

    chunks = []

    for page in document["pages"]:
        # Для первого эксперимента берём только страницу 1
        if page["page"] != 1:
            continue

        text = page["text"]
        start = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))
            fragment = text[start:end].strip()

            if fragment:
                chunks.append({
                    "source": page["source"],
                    "page": page["page"],
                    "text": fragment
                })

            if end == len(text):
                break

            start = end - overlap

    return chunks
