
from services.knowledge_base_service import load_knowledge_base
from services.search_service import search_chunks


def main():
    chunks = load_knowledge_base()

    print(f"\nВсего фрагментов в базе: {len(chunks)}")

    queries = [
        "Как ключевая ставка влияет на кредитование компаний?",
        "Какие риски существуют для металлургической отрасли?",
        "Каковы перспективы рынка золота?",
        "Что происходит с инфляцией в России?",
    ]

    for query in queries:
        print("\n" + "=" * 70)
        print(f"ЗАПРОС: {query}")
        print("=" * 70)

        results = search_chunks(query, chunks)

        print(f"Найдено фрагментов: {len(results)}")

        for index, result in enumerate(results, start=1):
            print(f"\nРезультат №{index}")
            print(f"Релевантность: {result['score']:.4f}")
            print(f"Источник: {result['source']}")
            print(f"Страница: {result['page']}")
            print(result["text"][:400])


if __name__ == "__main__":
    main()
