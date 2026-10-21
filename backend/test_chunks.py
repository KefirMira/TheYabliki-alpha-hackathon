
from pathlib import Path
from services.chunk_service import load_chunks

base_dir = Path(__file__).resolve().parent

json_path = (
    base_dir / "data" / "processed" / "policy_rate.json"
)

chunks = load_chunks(str(json_path))

print(f"Всего фрагментов: {len(chunks)}")

for index, chunk in enumerate(chunks[:3], start=1):
    print(f"\nФрагмент №{index}")
    print(f"Источник: {chunk['source']}")
    print(f"Страница: {chunk['page']}")
    print(f"Длина: {len(chunk['text'])} символов")
    print(chunk["text"][:300])
