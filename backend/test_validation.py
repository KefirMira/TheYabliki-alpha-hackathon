
from schemas.company import CompanyProfile
from services.validation_service import validate_analysis


def test_export_assumption():
    company = CompanyProfile(
        company_id="metal-001",
        industry="Металлургия",
        region="Московская область",
        revenue=150_000_000,
        credit_exposure=50_000_000
    )

    analysis = (
        "Компания не является экспортёром, "
        "поскольку находится в Московской области."
    )

    warnings = validate_analysis(analysis, company)

    assert len(warnings) == 1


def test_zero_credit_exposure():
    company = CompanyProfile(
        company_id="it-001",
        industry="Разработка программного обеспечения",
        region="Москва",
        revenue=30_000_000,
        credit_exposure=0
    )

    analysis = (
        "У компании нет долгов, "
        "поэтому ключевая ставка на неё не влияет."
    )

    warnings = validate_analysis(analysis, company)

    assert len(warnings) == 1


def test_correct_analysis():
    company = CompanyProfile(
        company_id="it-001",
        industry="Разработка программного обеспечения",
        region="Москва",
        revenue=30_000_000,
        credit_exposure=0
    )

    analysis = (
        "В профиле указана нулевая кредитная "
        "экспозиция. Данные об остальных "
        "обязательствах компании отсутствуют."
    )

    warnings = validate_analysis(analysis, company)

    assert warnings == []


def main():
    tests = [
        test_export_assumption,
        test_zero_credit_exposure,
        test_correct_analysis
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print("\nВсе проверки пройдены!")


if __name__ == "__main__":
    main()
