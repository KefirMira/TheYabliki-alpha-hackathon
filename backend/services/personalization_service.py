
from schemas.analysis import (
    CompanyAnalysisResponse,
    ValidationResult
)
from schemas.company import CompanyProfile

from services.analysis_gateway import analyze_with_rag
from services.company_context_service import external_transfer_guard, serialize_context, CONTEXT_RULES
from services.structured_analysis_service import (
    parse_structured_analysis
)
from services.validation_service import validate_analysis


async def analyze_for_company(
    news: str,
    company: CompanyProfile,
    *, _local_rag=None,
) -> dict:
    return await _analyze_for_company(news, company, with_evidence=False, local_rag=_local_rag)


async def analyze_for_company_with_evidence(news: str, company: CompanyProfile, *, _local_rag=None):
    return await _analyze_for_company(news, company, with_evidence=True, local_rag=_local_rag)


async def _analyze_for_company(news: str, company: CompanyProfile, *, with_evidence: bool, local_rag=None):
    """
    Возвращает структурированный анализ новости
    для конкретной компании.
    """

    context = company._ai_context
    if local_rag is None:
        external_transfer_guard(context)
    company_data = serialize_context(context) if context is not None else company.model_dump_json(
        indent=2,
        exclude_none=True
    )

    question = f"""
Проанализируй влияние новости на компанию.

ПРОФИЛЬ КОМПАНИИ:
{company_data}

НОВОСТЬ:
{news}

Верни только корректный JSON-объект.
Не добавляй Markdown, пояснения или текст вне JSON.

Структура JSON:
{{
    "relevance": "high",
    "summary": "Краткое описание влияния новости",
    "risks": [
        "Риск 1",
        "Риск 2"
    ],
    "opportunities": [
        "Возможность 1"
    ],
    "recommendations": [
        "Рекомендация 1"
    ]
}}

Правила:
- relevance: только high, medium, low или unknown.
- summary: 1-3 предложения.
- risks: список возможных рисков.
- opportunities: список возможных возможностей.
- recommendations: конкретные действия для компании.
- Если нет обоснованных пунктов, используй пустой список.
- Не выдумывай отсутствующие данные.
- Разделяй подтверждённые факты и предположения.
- Не делай вывод об экспорте по региону регистрации.
- Нулевая кредитная экспозиция не означает
  отсутствие всех долгов компании.
- Не считай отношение долга к выручке
  доказательством высокой долговой нагрузки.
- Для неподтверждённых выводов используй
  формулировки "возможно", "если", "при условии".
- Если используешь факты из аналитики,
  указывай номер источника в тексте.
"""

    if context is not None:
        question += CONTEXT_RULES
    rag_options = {"include_evidence": True} if with_evidence else {}
    rag_result = await (local_rag or analyze_with_rag)(
        question=question,
        search_query=news,
        **rag_options,
    )

    # Не пытаемся разбирать служебное сообщение
    # об отсутствии контекста как JSON
    if not rag_result["sources"]:
        raise ValueError(
            "Недостаточно аналитических материалов "
            "для структурированного анализа."
        )

    # Проверяем структуру ответа модели
    content = parse_structured_analysis(
        rag_result["analysis"]
    )

    # Проверяем содержимое на известные ошибки
    analysis_text = "\n".join([
        content.summary,
        *content.risks,
        *content.opportunities,
        *content.recommendations
    ])

    warnings = validate_analysis(
        analysis=analysis_text,
        company=company
    )

    response = CompanyAnalysisResponse(
        company_id=company.company_id,
        news=news,
        relevance=content.relevance,
        summary=content.summary,
        risks=content.risks,
        opportunities=content.opportunities,
        recommendations=content.recommendations,
        sources=rag_result["sources"],
        validation=ValidationResult(
            passed=len(warnings) == 0,
            warnings=warnings
        )
    )

    if with_evidence:
        from schemas.persisted_analysis import PersistableAnalysis

        return PersistableAnalysis(
            analysis=response,
            evidence=rag_result["evidence"],
            model_name=rag_result.get("model_name"),
            prompt_version="company-context-v1" if context is not None else "company-json-v1",
        )
    return response.model_dump()
