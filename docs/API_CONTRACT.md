> Обновление v1.22.0: 3 новых auth-операции, всего 14. Успешные domain JSON сохранены; 401/403 обязательны. Для приватных новостей требуется grant, в том числе при чтении карточки и COMPLETED. Таблица ниже описывает прежние domain payload; security-контракт имеет приоритет: [AUTH_ACCESS.md](AUTH_ACCESS.md).

# Контракт AI/backend v1.15.0

Проверен по обработчикам всех 11 операций. `/docs` и `/openapi.json` содержат актуальные схемы Pydantic. С v1.22.0 требуется индивидуальный Bearer для всех business API; legacy AI-endpoints закрыты. См. AUTH_ACCESS.md. JWT не используется. Даты ответов — ISO 8601; денежные Decimal профиля — JSON-строки. Ошибки не содержат DSN, SQL или секретов.

| Метод и путь | Запрос | Успех | Обработанные ошибки и ограничения |
|---|---|---|---|
| GET /health | нет | 200 `{status: "ok"}` | Только liveness; не проверяет зависимости |
| GET /ready | нет | 200 ReadinessResponse | 503 с тем же форматом; см. ниже |
| POST /api/analyze | AnalyzeRequest: news, минимум 1 символ | 200 AnalyzeResponse: analysis | 422 валидация, 502 строковый detail, 503 demo; верхнего лимита news нет, результат не сохраняется |
| POST /api/analyze-rag | AnalyzeRequest | 200 RAGResponse: analysis, sources | 422, 502 строковый detail, 503 demo; без сохранения. Источник: id/document/date/page/chunk_id/score. date может быть неполной датой или null |
| POST /api/analyze-company | CompanyAnalyzeRequest: news и CompanyProfile | 200 CompanyAnalysisResponse | 422 валидация либо строковый detail бизнес-ошибки; 502 строковый detail; 503 demo. Профиль передаёт клиент, БД не используется |
| GET /api/companies/{source_id} | source_id 1–200 символов | 200 CompanyProfileResponse | 404 COMPANY_NOT_FOUND, 422, 503 DATABASE_UNAVAILABLE. credit_exposure=null; source_id не является названием |
| POST /api/companies/{source_id}/analyses | CompanyAnalysisRequest: news.text 1–100000, news.title опционально 1–500; непустые | 201 CreatedCompanyAnalysis | 404 компания, 422, 502 AI, 503 demo/БД/сохранение/неопределённый статус. Создаёт MANUAL-новость |
| POST /api/companies/{source_id}/news/{news_id}/analyses | без тела; news_id положительный int64 | 201 новый / 200 сохранённый CreatedCompanyAnalysis | 409 RUNNING/retry/лимит/история; 404 компания/новость без запуска; 422 параметры или NEWS_CONTENT_UNAVAILABLE; 502 AI; 503 demo/БД/сохранение/статус. Новость не изменяется |
| GET /api/companies/{source_id}/insights | limit 1–100, default 20; cursor ≤2048 | 200 InsightFeed: items, next_cursor | 404 компания; 422 валидация/INVALID_CURSOR; 503 БД. Только COMPLETED; created_at DESC, id DESC. Курсор привязан к компании. Пустой список — 200 |
| GET /api/companies/{source_id}/insights/{insight_id} | insight_id положительный int64 | 200 InsightCard | 404 компания/инсайт, в том числе чужой или незавершённый; 422; 503 БД. Без LLM |
| POST /api/news | ExternalNewsInput | 201 создана / 200 дубликат: IngestedNews | 403 demo policy, 409 NEWS_IDENTITY_CONFLICT, 422, 503 DATABASE_UNAVAILABLE / NEWS_INGESTION_RETRY. Без AI и analysis_runs |

`CreatedCompanyAnalysis`: run_id, insight_id, news_id, status=COMPLETED, company_id (внешний source_id), analysis. Анализ содержит relevance, summary, risks, opportunities, recommendations, sources и validation. `InsightCard` возвращает также исходные evidence. Не заменяйте relevance выдуманными confidence/impact. Повтор POST сохранённой новости защищён по паре company_id/news_id: COMPLETED возвращается без LLM, RUNNING даёт 409. Ручной POST и legacy API такой защиты не имеют.

Для POST /api/news обязательны только title (1–500) и content (1–100000), непустые и без NUL. url, source_name, source_id, published_at, language необязательны. source_name: lowercase ASCII `[a-z0-9._-]`, до 100; source_id до 500, регистр сохраняется, без крайних ASCII whitespace. published_at требует timezone; language до 10. Неизвестные поля запрещены. Надёжный ключ: полная внешняя пара; URL — дополнительный. Без обоих идентификаторов повтор может создать другую запись. Канонизация сохраняет значимые query, регистр path и различие HTTP/HTTPS. Дубликат не обновляет данные, diagnostics описывают расхождения. Пара и URL, указывающие на разные записи, дают 409. Подробнее: [приём новостей](NEWS_INGESTION_API.md).

В demo все пять POST анализа возвращают 503 `AI_DISABLED_IN_DEMO`, даже если есть ключ. POST /api/news принимает только source_name=synthetic-demo, source_id с SYNTH- и URL без адреса либо на example.invalid/его поддомене. Это политика формата синтетических данных, а не семантическая проверка текста.

## Форматы ошибок

- Валидация FastAPI: `{"detail": [{"loc": ["body", "news"], "msg": "...", "type": "..."}]}`; дополнительные поля ошибки возможны.
- Ошибка сервисов: `{"detail": {"code": "...", "message": "..."}}`; ошибки сохранённого анализа могут содержать run_id. Неопределённый статус запуска нельзя трактовать как гарантированный FAILED.
- Старые LLM API сохраняют строковый detail для ошибок 502; /api/analyze-company также для бизнес-ошибки 422.

Схемы в `schemas/http_docs.py` используются только для OpenAPI, не фильтруют старые ответы и не меняют обработчики ошибок.

## Readiness PostgreSQL

Формат сохранён: `{"status":"ready|not_ready","checks":{"rag":true,"llm_config":true,"database":true}}`.

БД готова только при наличии всех 15 public-таблиц и объектов 004/005:

- news_external_source_name_check и news_external_source_id_check: CHECK, validated, точное определение из миграции;
- uq_news_external_source_identity: UNIQUE btree на news_articles, правильные ключи/порядок/предикат, COLLATE "C" обоих ключей, valid/ready/live.

Проверка выполняет только SELECT системных каталогов, без DDL, записи данных, исправлений или применения миграций. Общий timeout БД — 6 секунд. Ошибка соединения, доступа или несовпадение определения приводит к database=false и HTTP 503. В demo обязательна только БД; в full также непустой подготовленный RAG и конфигурация LLM. Проверка LLM не обращается к провайдеру и не подтверждает работоспособность ключа.

Сверка определения соответствует строгому механизму повторного применения 004 на PostgreSQL 16. Иная версия PostgreSQL или семантически эквивалентное, но иначе записанное ограничение может дать неготовность: это сигнал для проверки разработчиком БД, а не повод автоматически исправлять схему. Unicode whitespace в source_id пока отдельно не охватывается. Проверка не является полной проверкой всех столбцов, FK, прав записи или качества корпуса.

Существующий demo-том без 004 после обновления backend будет not_ready. Применение выполняется вручную после предварительной проверки и согласования по [инструкции миграции](NEWS_IDENTITY_MIGRATION.md); backend сам том не изменяет.

## Проверка

`python -m pytest backend/tests/test_openapi_contract.py backend/tests/test_readiness_identity.py -m "not integration"` — OpenAPI и API-статусы с подставной БД, без LLM.

Полный `backend/tests/run-profile-tests.ps1 -ComposeOverride <внешний override>` запускает также PostgreSQL-тесты определения объектов. Они создают отдельные UUID-БД только внутри нового изолированного тестового сервера. Проверка самого probe выполняется в read-only транзакции. Общая/production-БД не используется.

Итог проверки v1.14.1: 348 passed, 0 skipped на изолированной PostgreSQL 16.15, включая 13 сценариев состояния каталога и повторное применение 004. SQL-runner подтвердил 13 таблиц, round trip AI-фикстуры, ограничения и неизменность контрольных сумм. SDK LLM и внешние сетевые соединения заблокированы; использована существующая внешняя Docker-сеть и новые отдельные тома. Контейнеры остановлены, тома сохранены. Отдельный Docker smoke в этой версии не повторялся; проверки Compose-конфигурации входят в pytest. Есть предупреждение Starlette/httpx о будущем изменении test client.

## Дополнение v1.15.0

Readiness также сравнивает точную PostgreSQL 16 catalogue signature колонок, ограничений и индексов 005, включая validated и valid/ready/live. Отсутствующий или изменённый объект даёт database=false/503. Это fingerprint определения, а не security checksum. Старые demo-тома обновляются вручную, без автоматического DDL. Подробности claim, регистрации истории и административного retry: [ANALYSIS_JOBS.md](ANALYSIS_JOBS.md).
