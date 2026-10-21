
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def search_chunks(
    query: str,
    chunks: list[dict],
    top_k: int = 3
) -> list[dict]:

    if not query.strip() or not chunks or top_k <= 0:
        return []

    texts = [chunk["text"] for chunk in chunks]

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

    for index in ranked_indices[:top_k]:
        if scores[index] <= 0:
            continue

        results.append({
            **chunks[index],
            "score": float(scores[index])
        })

    return results
