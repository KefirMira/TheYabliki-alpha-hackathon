
from pathlib import Path

from services.chunk_service import load_chunks
from services.search_service import search_chunks

base_dir = Path(__file__).resolve().parent

json_path = (
    base_dir / "data" / "processed" / "policy_rate.json"
)

chunks = load_chunks(str(json_path))

query = (
    "Как сохранение ключевой ставки влияет "
    "на кредитование компаний?"
)

results = search_chunks(query, chunks)

print(f"Найдено фрагментов: {len(results)}")

for index, result in enumerate(results, start=1):
    print(f"\nРезультат №{index}")
    print(f"Релевантность: {result['score']:.4f}")
    print(f"Источник: {result['source']}")
    print(f"Страница: {result['page']}")
    print(result["text"][:500])
