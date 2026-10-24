# Чтение профиля компании из PostgreSQL

Версия: v1.6.0. Первый этап интеграции: только GET профиля и адаптер для существующего AI.
Ветка `codex/company-profile-db` создана от `feature/llm` (848da05). Инфраструктура PR №2 (458f857) — отдельная зависимость: 16 файлов БД не включаются повторно в коммит первого этапа. Для интеграционных тестов используется отдельный checkout. Исходные ветки не изменены.

## Конфигурация

Дополнительные рабочие зависимости: `backend/requirements-db.txt` (SQLAlchemy async + asyncpg). Основной `backend/requirements.txt` подключает этот файл; исходная UTF-16-кодировка сохранена.

`DATABASE_URL` берётся из окружения или `backend/.env`. Шаблон — `backend/.env.example`. Формат: `postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DATABASE`; специальные символы в реквизитах URL-кодировать. Реальный `.env` не добавлять в Git.
Рабочую роль с правом SELECT на companies и загрузку реальных данных готовит владелец БД. Приложение не выполняет DDL и не создаёт таблицы через ORM.

Движок и пул создаются в lifespan приложения; соединение открывается при запросе. Timeout подключения и SQL-команды — 5 секунд. При завершении пул освобождается. Отсутствие DATABASE_URL не мешает запуску health/старых маршрутов; профиль вернёт 503. URL с другим драйвером отвергается при запуске как ошибка конфигурации.

## API

`GET /api/companies/{source_id}` ищет внешний SYNTHETIC_U в `public.companies.source_id`. Внутренний id и source_data наружу не передаются.

Пример для синтетической фикстуры:

```json
{
  "company_id": "SYNTH-COMPANY-A",
  "name": "Synthetic Workshop A",
  "name_is_placeholder": false,
  "industry": "Synthetic manufacturing",
  "region": "Test region A",
  "revenue": "1000.25",
  "revenue_year": null,
  "client_status": "CLIENT",
  "credit_exposure": null
}
```

Денежные суммы возвращаются строкой из Decimal без преобразования во float. Неизвестная выручка — null. Имя, совпадающее с source_id, и пустое имя возвращаются как name=null, name_is_placeholder=true. Это сигнал фронтенду показывать идентификатор отдельно от названия.

404: `{"detail":{"code":"COMPANY_NOT_FOUND","message":"Компания не найдена"}}`.
503: `{"detail":{"code":"DATABASE_UNAVAILABLE","message":"База данных недоступна"}}`.
Ответ ошибки не содержит пароль, DSN, SQL и внутренние сообщения драйвера. Недопустимые параметры пути возвращают стандартную 422 FastAPI.

`CompanyProfileService.get_profile()` — адаптер для будущей интеграции AI: source_id → company_id, industry/region/revenue из companies, credit_exposure=None. Только в этом адаптере Decimal преобразуется во float, поскольку существующая AI-схема требует float. API и запись БД сохраняют точность. Существующий `/api/analyze-company` этот сервис пока не использует.

## Независимость от LLM

main больше не создаёт LLM-клиент при импорте. analysis_gateway откладывает импорт прежних сервисов до запроса анализа. RAG, personalization_service и обработчики `/api/analyze-company`, `/api/analyze-rag` сохранены. Обычный `/api/analyze` создаёт и закрывает клиент при запросе. Профиль и health не требуют LLM_API_KEY, LLM_BASE_URL или LLM_MODEL.

## Проверки

Отдельное окружение в корне репозитория (существующее backend/.venv не менять):

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements-profile-tests.txt
.venv/Scripts/python.exe -B -m pytest -c backend/pytest.ini backend/tests -m "not integration" -q
git worktree add --detach ../theyabliki-db-fixtures 458f857
powershell -NoProfile -ExecutionPolicy Bypass -File backend/tests/run-profile-tests.ps1 -DatabaseRoot ../theyabliki-db-fixtures/database
```

Параметр `DatabaseRoot` указывает на папку database отдельного checkout, а не на его корень. Существующий checkout PR №2 можно использовать вместо создания нового. После включения БД в общую базу ветки параметр можно опустить: по умолчанию скрипт ищет database в корне проекта. Отсутствие зависимости выявляется до запуска Docker.

Для интеграции нужны Docker Desktop Linux containers и Compose v2 с up --wait. По умолчанию используется 127.0.0.1:55435; другой порт задаётся DB_TEST_PORT до запуска. Скрипт создаёт новый случайный Compose-проект, контейнер и том, применяет неизменённые schema/002/003 и полностью синтетическую base fixture. Монтируются только файлы схемы, миграций и фикстур из PR №2, не private/ и не backend/.env.

Скрипт сравнивает контрольные суммы базовых данных до/после, останавливает свой контейнер и сохраняет том. Чужие контейнеры/тома не использует. Не выполнять volume prune или down -v без отдельного решения.

pytest-конфигурация ограничивает сбор новым backend/tests. Не включать старые test_llm.py и другие демонстрационные LLM-скрипты в этот набор. Тесты отключают загрузку .env, удаляют LLM-переменные только из собственного процесса и блокируют OpenAI SDK.

## Результат выполнения

22 октября 2026: **22 passed** (19 unit/контрактных + 3 интеграционных), 3.94 секунды. PostgreSQL 16.15, FastAPI 0.156.8, Pydantic 2.14.1, SQLAlchemy 2.0.55, asyncpg 0.32.0, Python 3.12.
Повторный прогон выполнен после исключения локальных копий инфраструктуры с DatabaseRoot из отдельного checkout PR №2 на коммите 458f857.
Изолированный проект: `theyabliki-profile-71d0ad96cfaf`; контейнер остановлен, том сохранён. Контрольные суммы синтетического baseline совпали. LLM не вызывалась, реальные CSV не загружались.
Один warning Starlette: текущий TestClient с httpx помечен deprecated в пользу httpx2; на прохождение тестов это не повлияло.

## Границы этапа

- Нет записи анализов, импорта CSV, авторизации и пользовательской фильтрации доступа.
- /health остаётся liveness-проверкой, не проверкой доступности БД.
- Конфликтующие исходные профили должен обрабатывать importer владельца БД; репозиторий опирается на UNIQUE(source_id).
- Профиль API сохраняет Decimal; существующий AI-профиль пока использует float.
- В runtime-запросах только SELECT, но ограничение прав роли на уровне PostgreSQL настраивает владелец БД.
- Реальное подключение старых аналитических маршрутов к провайдеру не проверялось; их контракт проверен с подставным анализатором.
- Первый этап фиксируется отдельным локальным коммитом v1.6.0; push, merge и PR не выполняются автоматически.
