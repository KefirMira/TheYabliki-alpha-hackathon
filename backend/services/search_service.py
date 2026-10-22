
import re

import numpy as np

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


LEGAL_MARKERS = [
    "не является индивидуальной инвестиционной рекомендацией",
    "не является публичной офертой",
    "лица, участвующие в подготовке",
    "маркет-мейкерами",
    "ограничение ответственности",
    "инвестиционного банка в отношении ценных бумаг",
    "ценные бумаги сопряжены со значительным риском",
    "инвесторы должны обсудить",
    "со своими финансовыми консультантами",
    "должны провести собственное исследование",
]


TOPIC_KEYWORDS = {
    "золот": ["gold", "золот"],
    "металлург": ["steel", "сталь", "металлург"],
    "инфляц": ["inflation", "инфляц"],
    "ставк": ["rate", "ставк", "дкп"],
    "кредит": ["credit", "кредит", "bond", "бонд"],
    "потреблен": ["consumption", "потреблен"],
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def is_legal_text(text: str) -> bool:
    normalized = normalize_text(text)

    return any(
        marker in normalized
        for marker in LEGAL_MARKERS
    )


def calculate_text_quality(text: str) -> float:
    """
    Понижает оценку коротких фрагментов
    и текста с большим количеством OCR-шума.
    """

    words = re.findall(
        r"[а-яёa-z]{3,}",
        text.lower()
    )

    if not words:
        return 0.4

    if len(words) < 15:
        return 0.5

    if len(words) < 40:
        return 0.8

    return 1.0


def calculate_topic_bonus(
    query: str,
    source: str,
    text: str
) -> float:
    """
    Небольшой бонус за тематическое
    совпадение запроса с документом.
    """

    normalized_query = normalize_text(query)
    normalized_source = normalize_text(source)
    normalized_text = normalize_text(text)

    bonus = 0.0

    for topic, keywords in TOPIC_KEYWORDS.items():
        if topic not in normalized_query:
            continue

        if any(
            keyword in normalized_source
            for keyword in keywords
        ):
            bonus += 0.04

        if any(
            keyword in normalized_text
            for keyword in keywords
        ):
            bonus += 0.02

    return min(bonus, 0.12)


def search_chunks(
    query: str,
    chunks: list[dict],
    top_k: int = 3
) -> list[dict]:

    if not query.strip() or not chunks or top_k <= 0:
        return []

    filtered_chunks = [
        chunk
        for chunk in chunks
        if chunk.get("text", "").strip()
        and not is_legal_text(chunk["text"])
    ]

    if not filtered_chunks:
        return []

    texts = [
        chunk["text"]
        for chunk in filtered_chunks
    ]

    # Поиск по словам
    word_vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2)
    )

    # Поиск по частям слов
    char_vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5)
    )

    try:
        word_matrix = word_vectorizer.fit_transform(
            [query] + texts
        )

        char_matrix = char_vectorizer.fit_transform(
            [query] + texts
        )

    except ValueError:
        return []

    word_scores = cosine_similarity(
        word_matrix[0:1],
        word_matrix[1:]
    )[0]

    char_scores = cosine_similarity(
        char_matrix[0:1],
        char_matrix[1:]
    )[0]

    combined_scores = (
        0.4 * word_scores
        + 0.6 * char_scores
    )

    ranked_results = []

    for index, similarity in enumerate(combined_scores):
        chunk = filtered_chunks[index]

        quality = calculate_text_quality(
            chunk["text"]
        )

        topic_bonus = calculate_topic_bonus(
            query=query,
            source=chunk["source"],
            text=chunk["text"]
        )

        score = (
            float(similarity) * quality
            + topic_bonus
        )

        if score <= 0:
            continue

        ranked_results.append({
            **chunk,
            "score": round(score, 4)
        })

    ranked_results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return ranked_results[:top_k]
