
import re

from schemas.company import CompanyProfile


def validate_analysis(
    analysis: str,
    company: CompanyProfile
) -> list[str]:
    """
    Проверяет аналитический ответ на известные
    неподтверждённые утверждения.

    Возвращает список предупреждений.
    Пустой список не гарантирует, что весь анализ верен.
    """

    warnings = []

    text = analysis.lower()

    # Проверка необоснованных выводов об экспорте
    export_patterns = (
        r"компания не является экспорт[её]ром",
        r"компания не экспортирует",
        r"компания не занимается экспортом",
    )

    for pattern in export_patterns:
        if re.search(pattern, text):
            warnings.append(
                "Обнаружено утверждение об отсутствии "
                "экспорта. Профиль компании не содержит "
                "данных об экспортной деятельности."
            )
            break

    # Проверка выводов о полном отсутствии долгов
    if company.credit_exposure == 0:
        debt_patterns = (
            r"у компании нет долгов",
            r"долговой нагрузки нет",
            r"компания не имеет долгов",
            r"полное отсутствие долгов",
        )

        for pattern in debt_patterns:
            if re.search(pattern, text):
                warnings.append(
                    "Нулевая кредитная экспозиция не "
                    "доказывает отсутствие всех долгов "
                    "и обязательств компании."
                )
                break

    return warnings
