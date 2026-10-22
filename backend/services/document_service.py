
import json
from pathlib import Path

from services.pdf_service import extract_pdf_text


BASE_DIR = Path(__file__).resolve().parent.parent

ANALYTICS_DIR = BASE_DIR / "data" / "analytics"
PROCESSED_DIR = BASE_DIR / "data" / "processed"


def process_document(
    pdf_path: str,
    output_path: str
) -> dict:
    """
    Обрабатывает один PDF и сохраняет
    извлечённый текст в JSON.
    """

    pages = extract_pdf_text(pdf_path)

    if not pages:
        raise ValueError(
            f"Не удалось извлечь текст из {pdf_path}"
        )

    result = {
        "document": Path(pdf_path).name,
        "pages": pages
    }

    output = Path(output_path)

    output.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # Сначала записываем во временный файл.
    # Если запись завершится ошибкой,
    # существующий JSON не будет затронут.
    temporary_output = output.with_suffix(".json.tmp")

    try:
        with temporary_output.open(
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                result,
                file,
                ensure_ascii=False,
                indent=2
            )

        temporary_output.replace(output)

    finally:
        if temporary_output.exists():
            temporary_output.unlink()

    print(f"Документ обработан: {result['document']}")
    print(f"Страниц с текстом: {len(pages)}")
    print(f"Результат сохранён: {output}")

    return result


def process_all_documents() -> dict:
    """
    Обрабатывает все PDF из папки analytics.

    Уже существующие JSON пропускаются.
    """

    ANALYTICS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    pdf_files = sorted(
        ANALYTICS_DIR.glob("*.pdf")
    )

    if not pdf_files:
        print("PDF-документы не найдены.")

        return {
            "processed": 0,
            "skipped": 0,
            "failed": []
        }

    processed = 0
    skipped = 0
    failed = []

    for pdf_path in pdf_files:
        output_path = (
            PROCESSED_DIR / f"{pdf_path.stem}.json"
        )

        # Не перезаписываем готовые документы
        if output_path.exists():
            print(
                f"Пропущен: {pdf_path.name} "
                "(JSON уже существует)"
            )

            skipped += 1
            continue

        print(f"\nОбрабатываем: {pdf_path.name}")

        try:
            process_document(
                pdf_path=str(pdf_path),
                output_path=str(output_path)
            )

            processed += 1

        except Exception as error:
            print(
                f"Ошибка обработки {pdf_path.name}: "
                f"{error}"
            )

            failed.append(pdf_path.name)

    print("\n========== ИТОГ ==========")
    print(f"Новых документов: {processed}")
    print(f"Пропущено: {skipped}")
    print(f"Ошибок: {len(failed)}")
    print("==========================")

    return {
        "processed": processed,
        "skipped": skipped,
        "failed": failed
    }
