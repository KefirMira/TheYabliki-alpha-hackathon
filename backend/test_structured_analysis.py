
from services.structured_analysis_service import (
    parse_structured_analysis
)


def test_valid_json():
    text = """
{
    "relevance": "high",
    "summary": "Новость влияет на стоимость кредитования.",
    "risks": ["Удорожание рефинансирования"],
    "opportunities": [],
    "recommendations": ["Проверить структуру долга"]
}
"""

    result = parse_structured_analysis(text)

    assert result.relevance == "high"
    assert len(result.risks) == 1
    assert result.opportunities == []


def test_markdown_json():
    text = '''```json
{
    "relevance": "medium",
    "summary": "Возможно косвенное влияние.",
    "risks": [],
    "opportunities": [],
    "recommendations": []
}
```'''

    result = parse_structured_analysis(text)

    assert result.relevance == "medium"


def test_invalid_relevance():
    text = """
{
    "relevance": "very_high",
    "summary": "Описание",
    "risks": [],
    "opportunities": [],
    "recommendations": []
}
"""

    try:
        parse_structured_analysis(text)
    except ValueError:
        return

    raise AssertionError(
        "Некорректное значение relevance должно вызывать ошибку."
    )


def test_invalid_json():
    text = "Это обычный текст, а не JSON"

    try:
        parse_structured_analysis(text)
    except ValueError:
        return

    raise AssertionError(
        "Некорректный JSON должен вызывать ошибку."
    )


def main():
    tests = [
        test_valid_json,
        test_markdown_json,
        test_invalid_relevance,
        test_invalid_json
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print("\nВсе тесты структурированного анализа пройдены!")


if __name__ == "__main__":
    main()
