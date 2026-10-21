
from pathlib import Path
from services.pdf_service import extract_pdf_text

pdf_path = (
    Path(__file__).resolve().parent
    / "data"
    / "analytics"
    / "policy_rate.pdf"
)

pages = extract_pdf_text(str(pdf_path))

print(f"\nСтраниц с текстом: {len(pages)}")

for page in pages[:2]:
    print(f"\nДокумент: {page['source']}")
    print(f"Страница: {page['page']}")
    print("-" * 50)
    print(page["text"][:1000])
