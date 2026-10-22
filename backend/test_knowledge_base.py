
from collections import Counter

from services.knowledge_base_service import (
    load_knowledge_base
)


def main():
    chunks = load_knowledge_base()

    print("\nВсего фрагментов:", len(chunks))

    sources = Counter(
        chunk["source"]
        for chunk in chunks
    )

    print("\nДокументы в базе:")

    for document, count in sources.items():
        print(f"{document}: {count} фрагментов")

    assert chunks, "База знаний пуста"

    print("\nПроверка базы знаний пройдена!")


if __name__ == "__main__":
    main()
