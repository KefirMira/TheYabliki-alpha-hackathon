
from schemas.company import CompanyProfile
from services.rag_service import analyze_with_rag


async def analyze_for_company(
    news: str,
    company: CompanyProfile
) -> dict:
    """
    Анализирует новость с учётом профиля компании.
    """

    # Преобразуем профиль компании в JSON
    company_data = company.model_dump_json(
        indent=2,
        exclude_none=True
    )

    # Формируем персонализированный промпт
    question = f"""
Проанализируй новость применительно к конкретной компании.

ПРОФИЛЬ КОМПАНИИ:
{company_data}

НОВОСТЬ:
{news}

Подготовь анализ по следующей структуре:

1. Суть события.
2. Почему новость важна или не важна для компании.
3. Возможные риски.
4. Возможные возможности.
5. Что компании стоит проверить или предпринять.
6. Какие выводы подтверждаются аналитикой Альфа-Банка.

Требования:
- Учитывай отрасль и финансовые характеристики компании.
- Не выдумывай отсутствующие данные.
- Не утверждай наличие проблем без подтверждения.
- Разделяй факты и предположения.
- Если данных недостаточно, укажи это.
- Не считай отношение долга к выручке
  доказательством высокой долговой нагрузки.
"""

    # Полный промпт отправляем в LLM,
    # а поиск выполняем только по новости
    result = await analyze_with_rag(
        question=question,
        search_query=news
    )

    return {
        "company_id": company.company_id,
        "news": news,
        "analysis": result["analysis"],
        "sources": result["sources"]
    }
