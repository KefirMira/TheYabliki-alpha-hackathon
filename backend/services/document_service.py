
import json
from pathlib import Path

from services.pdf_service import extract_pdf_text


def process_document(pdf_path: str, output_path: str):
    pages = extract_pdf_text(pdf_path)

    result = {
        "document": Path(pdf_path).name,
        "pages": pages
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8") as file:
        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(f"Документ обработан: {result['document']}")
    print(f"Страниц с текстом: {len(pages)}")
    print(f"Результат сохранён: {output}")
