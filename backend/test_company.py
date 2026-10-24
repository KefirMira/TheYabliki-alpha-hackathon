
from pydantic import ValidationError

from schemas.company import CompanyProfile


company = CompanyProfile(
    company_id="test-001",
    industry="Металлургия",
    region="Московская область",
    revenue=150_000_000,
    credit_exposure=50_000_000
)

print("Профиль компании:")
print(company.model_dump_json(indent=2))

# Проверяем, что отрицательная выручка запрещена
try:
    CompanyProfile(
        company_id="test-002",
        revenue=-100
    )
except ValidationError:
    print("\nПроверка отрицательной выручки: успешно")
