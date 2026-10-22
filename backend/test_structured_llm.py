
import asyncio
import json

from schemas.company import CompanyProfile
from services.personalization_service import analyze_for_company


async def main():
    news = (
        "Центральный банк России сохранил ключевую "
        "ставку на уровне 14%. Регулятор отметил "
        "сохранение инфляционных рисков."
    )

    company = CompanyProfile(
        company_id="metal-001",
        industry="Металлургия",
        region="Московская область",
        revenue=150_000_000,
        credit_exposure=50_000_000
    )

    print("Запускаем структурированный анализ...")

    try:
        result = await analyze_for_company(
            news=news,
            company=company
        )

        print("\nРЕЗУЛЬТАТ:")
        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2
            )
        )

        print("\nПРОВЕРКА:")
        print("Значимость:", result["relevance"])
        print("Рисков:", len(result["risks"]))
        print("Возможностей:", len(result["opportunities"]))
        print("Рекомендаций:", len(result["recommendations"]))
        print("Источников:", len(result["sources"]))
        print(
            "Валидация:",
            result["validation"]["passed"]
        )

    except Exception as error:
        print("\nОШИБКА:")
        print(type(error).__name__)
        print(str(error))


if __name__ == "__main__":
    asyncio.run(main())
