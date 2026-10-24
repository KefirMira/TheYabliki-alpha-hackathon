
from pathlib import Path

from services.document_service import process_document

base_dir = Path(__file__).resolve().parent

pdf_path = base_dir / "data" / "analytics" / "policy_rate.pdf"

output_path = (
    base_dir / "data" / "processed" / "policy_rate.json"
)

process_document(
    str(pdf_path),
    str(output_path)
)
