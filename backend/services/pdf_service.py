
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image


# Путь к установленной программе Tesseract
pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


def extract_pdf_text(file_path: str) -> list[dict]:
    pages = []

    with pymupdf.open(file_path) as document:
        for page_number, page in enumerate(document, start=1):

            # Сначала пробуем извлечь обычный текст
            text = page.get_text("text").strip()

            # Если текстового слоя нет — используем OCR
            if not text:
                print(f"Распознаём страницу {page_number}...")

                pix = page.get_pixmap(
                    matrix=pymupdf.Matrix(2, 2),
                    alpha=False
                )

                image = Image.frombytes(
                    "RGB",
                    (pix.width, pix.height),
                    pix.samples
                )

                text = pytesseract.image_to_string(
                    image,
                    lang="rus+eng"
                ).strip()

            if not text:
                print(f"Страница {page_number}: текст не найден")
                continue

            pages.append({
                "source": Path(file_path).name,
                "page": page_number,
                "text": text
            })

    return pages
