
import asyncio

from schemas.company import CompanyProfile
from services.personalization_service import analyze_for_company


async def main():
    news = (
        "Центральный банк России сохранил ключевую "
        "ставку на уровне 14%. Регулятор отметил "
        "сохранение инфляционных рисков."
    )

    companies = [
        CompanyProfile(
            company_id="metal-001",
            industry="Металлургия",
            region="Московская область",
            revenue=150_000_000,
            credit_exposure=50_000_000
        ),
        CompanyProfile(
            company_id="it-001",
            industry="Разработка программного обеспечения",
            region="Москва",
            revenue=30_000_000,
            credit_exposure=0
        )
    ]

    for company in companies:
        print("\n" + "=" * 60)
        print(f"Компания: {company.company_id}")
        print(f"Отрасль: {company.industry}")

        result = await analyze_for_company(news, company)

        print("\nАНАЛИЗ:")
        print(result["analysis"])

        print("\nИСТОЧНИКИ:")
        for source in result["sources"]:
            print(
                f"{source['document']}, "
                f"стр. {source['page']}"
            )


if __name__ == "__main__":
    asyncio.run(main())
