
import json
import re
from pathlib import Path


def split_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200
) -> list[str]:
    """
    Разбивает текст на фрагменты.

    Старается сохранять границы слов
    и добавляет пересечение между фрагментами.
    """

    if chunk_size <= 0 or not 0 <= overlap < chunk_size:
        raise ValueError("Некорректные параметры разбиения")

    # Нормализуем пробелы и переносы строк
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        # Ищем ближайший пробел перед концом фрагмента
        if end < len(text):
            last_space = text.rfind(" ", start, end)

            if last_space > start:
                end = last_space

        fragment = text[start:end].strip()

        if fragment:
            chunks.append(fragment)

        if end >= len(text):
            break

        # Следующий фрагмент частично повторяет предыдущий
        next_start = max(0, end - overlap)

        # Перемещаем начало к границе слова
        if next_start > 0:
            next_space = text.find(" ", next_start, end)

            if next_space != -1:
                next_start = next_space + 1

        # Защита от бесконечного цикла
        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


def load_chunks(
    json_path: str,
    chunk_size: int = 1000,
    overlap: int = 200
) -> list[dict]:
    """
    Загружает все страницы JSON-документа
    и разбивает их на фрагменты.
    """

    if chunk_size <= 0 or not 0 <= overlap < chunk_size:
        raise ValueError("Некорректные параметры разбиения")

    with Path(json_path).open(
        "r",
        encoding="utf-8"
    ) as file:
        document = json.load(file)

    chunks = []

    # Теперь обрабатываем ВСЕ страницы
    for page in document["pages"]:
        text = page.get("text", "")

        fragments = split_text(
            text=text,
            chunk_size=chunk_size,
            overlap=overlap
        )

        for index, fragment in enumerate(
            fragments,
            start=1
        ):
            chunks.append({
                "source": page.get(
                    "source",
                    document.get("document", "unknown")
                ),
                "page": page["page"],
                "chunk_id": index,
                "text": fragment
            })

    return chunks
