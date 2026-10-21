
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# Фразы, характерные для служебных частей документов
SERVICE_MARKERS = (
    "не является индивидуальной инвестиционной рекомендацией",
    "ограничение ответственности",
    "раскрытие информации",
    "все права защищены",
)


def is_service_chunk(chunk: dict) -> bool:
    """
    Проверяет, является ли фрагмент служебным.
    """

    text = chunk.get("text", "").strip().lower()

    if not text:
        return True

    return any(
        marker in text
        for marker in SERVICE_MARKERS
    )


def search_chunks(
    query: str,
    chunks: list[dict],
    top_k: int = 3
) -> list[dict]:
    """
    Ищет наиболее подходящие фрагменты
    с использованием TF-IDF.
    """

    if not query.strip() or not chunks or top_k <= 0:
        return []

    # Убираем служебные фрагменты
    filtered_chunks = [
        chunk
        for chunk in chunks
        if not is_service_chunk(chunk)
    ]

    if not filtered_chunks:
        return []

    texts = [
        chunk["text"]
        for chunk in filtered_chunks
    ]

    vectorizer = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2)
    )

    matrix = vectorizer.fit_transform(texts)
    query_vector = vectorizer.transform([query])

    scores = cosine_similarity(
        query_vector,
        matrix
    )[0]

    ranked_indices = scores.argsort()[::-1]

    results = []

    for index in ranked_indices:
        if len(results) >= top_k:
            break

        if scores[index] <= 0:
            continue

        results.append({
            **filtered_chunks[index],
            "score": float(scores[index])
        })

    return results
