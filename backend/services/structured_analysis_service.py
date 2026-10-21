
import json
import re

from pydantic import ValidationError

from schemas.analysis import AnalysisContent


def parse_structured_analysis(text: str) -> AnalysisContent:
    """
    Преобразует JSON-ответ LLM в Pydantic-модель.
    """

    cleaned = text.strip()

    # Удаляем Markdown-обёртку, если модель её добавила
    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned
    )

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ValueError(
            "LLM вернула некорректный JSON."
        ) from error

    try:
        return AnalysisContent.model_validate(data)
    except ValidationError as error:
        raise ValueError(
            "JSON от LLM не соответствует схеме анализа."
        ) from error
