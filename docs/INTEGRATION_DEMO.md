# Синтетическое интеграционное демо v1.24.1

Это отдельное окружение, не `compose.frontend.yml` и не импортированные CSV.
Требуются Docker Desktop с Linux containers и Docker Compose v2. Frontend не изменяется.
Ниже команды PowerShell из корня репозитория. Они не используют Python на хосте.

## Запуск и seed

```powershell
# Новый локальный пароль PostgreSQL, только в памяти текущего терминала.
# При повторном запуске существующего тома нужен тот же пароль PostgreSQL.
$env:INTEGRATION_DEMO_DB_PASSWORD = [guid]::NewGuid().ToString('N')
$env:INTEGRATION_DEMO_PORT = '8000'
docker compose -p pulse-integration-demo -f compose.integration-demo.yml build backend
docker compose -p pulse-integration-demo -f compose.integration-demo.yml up -d --wait postgres backend

# По умолчанию только план, без создания компаний/аккаунтов.
docker compose -p pulse-integration-demo -f compose.integration-demo.yml run --rm seed

# Два независимых пароля вводятся через getpass дважды, не через argv/.env.
docker compose -p pulse-integration-demo -f compose.integration-demo.yml run --rm seed python -B -m integration_demo --expected-database test_integration_demo --apply --confirm-isolated
```

Из контейнера seed соединение идёт на loopback **его PostgreSQL namespace**.
Порт PostgreSQL на хост не публикуется. Адрес, драйвер, явный порт, имя
`test_*`, отсутствие URL-query и комментарий БД
`pulse:isolated-integration-demo:v1` проверяются до записи. Маркер устанавливает
только init нового выделенного тома; CLI не маркирует произвольную БД.
Маркер — дополнительный предохранитель, не доказательство доверия к удалённому серверу.
Не переносите его в существующую/shared БД.

Seed принимает только пустую БД либо собственную неизменённую фикстуру.
Создаёт 3 компании, 2 Argon2id-аккаунта, 3 memberships только на чтение,
3 приватные новости, 3 grants, 3 COMPLETED runs, 3 инсайта и 3 evidence.
Все цифры и названия вымышлены. Новых jobs/attempts и SDK-вызовов нет.

| Логин | Компании | Инсайты |
|---|---|---|
| `synthetic-demo-a` | `DEMO-001`, `DEMO-003` | 2 у DEMO-001; пустая история у DEMO-003 |
| `synthetic-demo-b` | `DEMO-002` | 1 |

Повторите ту же команду с теми же паролями: `state=UNCHANGED`.
Пароли не сбрасываются; сессии не отзываются. Контрольная сумма охватывает
профили, пользователей, grants, memberships, новости, runs, инсайты, evidence и alias.
Изменённая фикстура, иной пароль или непустая БД при первом запуске приводят к отказу без перезаписи.
Все записи выполняются в одной транзакции под advisory lock; ошибка откатывает seed целиком.
Сессии не входят в checksum: вход/выход не мешают повторному seed.
Обычные изменения демо-новостей/профилей намеренно делают seed неповторяемым до ручной проверки;
не удаляйте и не исправляйте данные автоматически.

На хосте с установленным backend допустим тот же CLI:
`PYTHONPATH=backend`, `INTEGRATION_DEMO_DATABASE_URL` — выделенный loopback
`postgresql+asyncpg://...:port/test_...`, затем `python -B -m integration_demo
--expected-database test_... [--apply --confirm-isolated]`. DSN не выводите в отчёт/логи.

Начальная Docker-сборка устанавливает зафиксированные зависимости из Python index:
для неё нужен сетевой доступ или заранее подготовленный слой зависимостей.
Compose не содержит production-настроек; PostgreSQL-role этого локального демо не
предназначена для production. Внешнюю тестовую сеть при необходимости подключайте
только override-файлом; используйте уникальное DNS-имя своего контейнера PostgreSQL,
а не общий alias `postgres` нескольких проектов.

## HTTP-контракт для frontend

Backend: `http://localhost:8000`; Swagger: `http://localhost:8000/docs`.
CORS разрешает `http://localhost:5173`. Проверяйте `/health` и `/ready`;
готовность БД не означает доступность AI. `AI_MODE=demo`, ключ и endpoint LLM пусты.

1. `POST /api/auth/login`, JSON `{"login":"synthetic-demo-a","password":"<введённый пароль>"}`.
   Ответ 200: `{"access_token":"<секретный индивидуальный токен>","token_type":"bearer","expires_in":3600}`.
2. На всех следующих запросах передавать `Authorization: Bearer <access_token>`.
3. `GET /api/me`: `{user_id,login,companies:[{source_id,name,can_analyze:false}]}`.
   Это список доступных компаний, отдельный list-companies endpoint не нужен.
4. `GET /api/companies/DEMO-001`: профиль `{company_id,name,name_is_placeholder,industry,region,revenue,revenue_year,client_status,credit_exposure}`.
   Decimal возвращается строкой. Не добавлять неизвестную валюту.
   У `DEMO-003` выручка/год отсутствуют и возвращаются `null`.
5. `GET /api/companies/DEMO-001/insights?limit=20`: `{items:[{insight_id,run_id,company_id,type,relevance,summary,created_at,status}],next_cursor:null}`.
   Для следующей страницы передавать непрозрачный `cursor` из ответа.
   `GET /api/companies/DEMO-003/insights` → `{"items":[],"next_cursor":null}`.
6. Взять `insight_id` из ленты; `GET /api/companies/DEMO-001/insights/{insight_id}`:
   поля ленты плюс `news`, `risks`, `opportunities`, `recommendations`, `validation`, `sources`, `evidence`.
7. `POST /api/auth/logout` с Bearer → **204 и пустое тело**. Не вызывать `response.json()`.
   Повторный запрос с отозванным токеном → 401.

Ошибки имеют `{detail:{code,message}}` (валидация FastAPI 422 имеет стандартный массив detail):

- **401** `AUTHENTICATION_REQUIRED`: нет/просрочена/отозвана сессия либо неверный пароль.
- **403** `ACCESS_DENIED`: чужая компания/новость/инсайт или отсутствие права записи.
  Несуществующая чужая сущность не отличима от запрещённой. Не интерпретировать 403 как пустую ленту.
- **422**: некорректный body/path/query; **429**: login rate limit, уважать Retry-After.
- **503**: БД недоступна либо операция анализа запрещена политикой/режимом.
  `GET .../capabilities` объясняет ограничения. Внешний DB-контекст по-прежнему заблокирован.

Токен не выводить в console/логи/URL. Локальный frontend demo-login пока не создаёт
серверную сессию: frontend-команде необходимо подключить login/me, Bearer, обработку
401/403, выбор компаний из me и logout 204. Обхода ACL для старого demo-login нет.

## Источники и ограничения

Новый evidence имеет `evidence_type=DOCUMENT`, а не безусловный `PDF`.
`sources[].provenance` содержит `declared_format` (TXT/PDF/UNKNOWN только по расширению),
`format_verified:false`, `publisher:null`, `attribution_status:UNKNOWN`.
Это не проверка байтов документа и не подтверждение авторства банка.
У демо дополнительно `synthetic:true`. Старые `PDF` без сохранённого подтверждения
формата проецируются как `DOCUMENT` без изменения истории. При явной серверной
отметке `provenance.format_verified:true`, `declared_format:PDF` и точном совпадении
документа, страницы и chunk исторический тип `PDF` сохраняется. Противоречащие друг
другу записи не считаются подтверждением. Сохранённые publisher и атрибуция не
переписываются: проверенный PDF может иметь неизвестного или небанковского издателя.
Эта проекция не проверяет байты файлов заново; существующий тип `PDF`, расширение
и имя файла сами по себе не подтверждают формат. Новые SDK-результаты не могут
самостоятельно установить отметку проверки: repository записывает `format_verified:false`.
Исходные текст, id, страницы,
chunk, даты и сохранённые поля источника остаются доступны.
Frontend не должен превращать тип/имя файла в «Позицию Альфа-Банка».
В существующем frontend mapper это ещё требуется исправить: для подтверждённого
PDF неизвестного/другого издателя нельзя подставлять банковское авторство.
Семантическая подтверждённость и `validation.passed` не равнозначны финансовой достоверности.

Реальный AI, RSS, загрузка документов, редактор профиля и уведомления этим seed не реализуются.
Демо предназначено для чтения: `can_analyze=false`. Полноценный E2E анализа не заявляется.

```powershell
docker compose -p pulse-integration-demo -f compose.integration-demo.yml logs --tail 100 backend postgres
docker compose -p pulse-integration-demo -f compose.integration-demo.yml stop
```

`stop` сохраняет сеть/том. Не использовать prune или `down -v`.

## Проверка v1.24.1 от 25.10.2026

В отдельном Docker project `pulse-integration-v1241-check3-20261025` проверены
маркер, собственный новый том и отсутствие host-порта PostgreSQL. Seed дал
`CREATED`, затем `UNCHANGED`, в том числе после login/logout. В БД: 3 компании,
2 пользователя, 3 memberships, 3 news grants, 3 инсайта и 0 attempts.

Успешны **23 настоящие loopback HTTP-проверки**:

| Проверка | Ответ |
|---|---|
| health, ready | 200; database=true |
| login, me, разрешённый профиль | 200 |
| лента, pagination, карточка | 200 |
| пустая история DEMO-003 | 200, items=[], next_cursor=null |
| отсутствующая выручка DEMO-003 | null |
| без сессии, неверный пароль, токен после logout | 401 |
| чужой профиль/инсайт, неизвестный ID | 403 |
| capabilities | 200 |
| logout | 204, пустое тело |
| CORS preflight Authorization с localhost:5173 | 200, разрешённые origin/header |

У новой сборки исходников сверены хеши рабочих файлов внутри контейнера.
Из-за отключённой сети полная установка зависимостей исходным Dockerfile не
прошла: недоступна загрузка `annotated-doc==0.0.5`. Поэтому smoke использовал
свежий слой исходников поверх ранее проверенного dependency image
`pulse-synthetic-gateway-v1240-check:20261025`. Чистая установка зависимостей
без кэша и с доступом к Python index в этой проверке не подтверждена.
Контейнеры проверки остановлены, тома и сеть сохранены; реальные LLM не вызывались.
Подробный локальный отчёт: `backend/data/integration_demo_check/report.json`
(исключён из Git; паролей и токенов не содержит).

Профильный прогон auth/insights/persistence/Docker: **45 passed**; окончательный
прогон 12 новых проверок seed/provenance/Compose: **12 passed** (наборы частично
пересекаются). Полный безопасный прогон backend + parser с PostgreSQL integration:
**1013 passed, 0 skipped**, 413,63 секунды. Базовая тестовая БД сохранена без
изменений; внешняя сеть и реальные SDK-вызовы были заблокированы.
Первый полный прогон обнаружил ошибку нового config-теста: он не включал Compose
profile `seed`. После исправления теста финальный полный прогон успешен.

## Состав поставки и локальные артефакты

В v1.24.1 входят ровно **13 файлов**:

1. `backend/.dockerignore`
2. `backend/Dockerfile`
3. `backend/fixtures/integration_demo.sql`
4. `backend/integration_demo.py`
5. `backend/repositories/company_analysis_repository.py`
6. `backend/repositories/evidence_repository.py`
7. `backend/services/insight_service.py`
8. `backend/services/source_provenance.py`
9. `backend/tests/test_auth_integration_demo.py`
10. `backend/tests/test_source_provenance.py`
11. `compose.integration-demo.yml`
12. `database/integration-demo-marker.sql`
13. `docs/INTEGRATION_DEMO.md`

`backend/fixtures/integration_demo.sql` — обязательная синтетическая фикстура,
читаемая CLI и включённая в Docker build context/image. Это не реальный CSV.
`backend/data/integration_demo_check/run.py` — только локальный вспомогательный
HTTP-smoke, не зависимость CLI/образа. Он, `report.json`, Docker overrides и
остальные артефакты под `backend/data/` исключены из Git и Docker context.
Предыдущие незакоммиченные документы аудита в поставку не входят.

Финальная проверка перед коммитом: **59 passed, 0 skipped** в профильном наборе
seed/provenance/auth/insights/persistence/Docker. Добавлены регрессии на сохранение
подтверждённого PDF, банковского/небанковского/неизвестного издателя, отсутствие
переноса подтверждения между разными фрагментами и упаковку SQL-фикстуры.
Предыдущий полный прогон 1013 тестов относится к состоянию до этой финальной
корректировки проекции; после неё повторены затронутые проверки, полный набор
повторно не запускался.

Повторный Docker smoke из финальных исходников: **27 HTTP-проверок** в собственном
project `pulse-integration-v1241-review-20261025`. Дополнительно проверены карточки
подтверждённого исторического PDF с неизвестным и независимым издателем: тип,
издатель, текст evidence и сохранённая история не искажаются. Синтетическая фикстура
после проверки восстановлена и seed снова вернул `UNCHANGED`. Сборка использовала
тот же проверенный dependency image без сети; ограничение чистой установки
зависимостей остаётся. Собственные контейнеры остановлены, том и сеть сохранены.
Локальный отчёт `backend/data/integration_demo_check/final-review-report.json`
также исключён из Git и не является файлом поставки.
