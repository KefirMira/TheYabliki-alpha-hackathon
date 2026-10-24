# Capabilities конкретной компании — v1.22.1

Новый read-only endpoint: **GET `/api/companies/{source_id}/capabilities`**.
`source_id`: строка длиной 1–200, идентификатор `companies.source_id`.
Тела и дополнительных query-параметров нет. Обязателен индивидуальный
`Authorization: Bearer <token>`; токен получать через `/api/auth/login` и не
сохранять в командную строку/отчёт. Проверяются активная сессия и membership.
Ответы `/api/*` по-прежнему имеют `Cache-Control: no-store`.

## Смысл состояний

| state | Значение |
|---|---|
| AVAILABLE | Обработчик реализован и разрешён текущему пользователю при перечисленных conditions; не обещает наличие данных, валидность будущего ввода или успешность следующего запроса |
| BLOCKED | Известен хотя бы один запрет: права, режим или политика передачи |
| UNAVAILABLE | Публичная операция не предоставлена; например, retry существует только в административном инструменте |
| UNKNOWN | Не хватает данных для решения; нельзя переводить в UI как разрешение/успех |

Наличие endpoint, LLM env или `ready.checks.llm_config=true` не делает новый
анализ доступным. Capabilities не является health-check провайдера, проверкой
финансовой достоверности или разрешением на внешнюю передачу. Оно не создаёт
новость/job/attempt/insight, не резервирует оплату и не разрешает retry.

## Точный JSON-контракт 200

`company_id`: запрошенный source_id, только после ACL; `mode`: `demo` или `full`.
`operations` содержит ровно шесть ключей ниже. У каждого:

- `state`: одно из четырёх состояний;
- `reasons`: массив `{category, code}`, пустой для AVAILABLE;
- `conditions`: массив кодов условий, которые проверяются целевым endpoint.

| operations key | Правило |
|---|---|
| read_profile | AVAILABLE после membership |
| read_insights | AVAILABLE; `NEWS_GRANT_REQUIRED`, `VISIBLE_COMPLETED_INSIGHTS_ONLY`; это не утверждение о непустой ленте или наличии карточки |
| submit_news | AVAILABLE; `REQUEST_VALIDATION_REQUIRED`; в demo также `DEMO_SYNTHETIC_NEWS_ONLY`. Приём новости требует сессию, а не can_analyze; приватный чужой дубликат всё равно даст 403 |
| analyze_new | BLOCKED при отсутствии can_analyze, demo или запрете передачи DB-контекста. В текущей реализации data-policy блокирует новый внешний анализ и в full. Даже если guard когда-либо разрешит передачу, без проверки входа/исполнителя/провайдера ответ будет UNKNOWN |
| reuse_completed | BLOCKED без can_analyze или в demo (demo блокирует и cache); иначе UNKNOWN, поскольку news grant, существование/целостность COMPLETED и содержимое новости не проверялись |
| retry_analysis | UNAVAILABLE / ADMINISTRATIVE_RETRY_ONLY; прежний admin-review, лимит попыток и fencing сохранены |

Для analyze_new conditions: `REQUEST_VALIDATION_REQUIRED`, `NEWS_GRANT_REQUIRED`,
`EXISTING_JOB_AND_RETRY_POLICY_APPLY`. Последнее распространяется на saved-news
путь; ручной POST `/{source_id}/analyses` по-прежнему не идемпотентен.
Для reuse_completed: `NEWS_GRANT_REQUIRED`, `COMPLETED_RESULT_REQUIRED`,
`EXISTING_JOB_AND_RETRY_POLICY_APPLY`. Для retry_analysis — только последнее.
Для read_profile conditions пусты.

`external_provider` всегда имеет форму:

```json
{"state":"UNKNOWN","reason":{"category":"PROVIDER","code":"PROVIDER_NOT_PROBED"}}
```

Не проверяются шлюз, quota/баланс, тариф, доступность модели, RAG-корпус, credentials
или readiness таблиц анализа. Конфигурация провайдера, URL, ключи, DSN и строки
контекста в ответ не попадают. Отсутствие проверки не означает доступность.

| category | reason code | Значение |
|---|---|---|
| ACCESS | ANALYSIS_PERMISSION_REQUIRED | Нет can_analyze; чтение своей компании от этого не запрещено |
| MODE | AI_DISABLED_IN_DEMO | Существующая общая политика demo запрещает AI POST, включая cache |
| DATA_POLICY | COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED | Существующий guard запрещает внешний анализ DB-контекста |
| REQUEST | NEWS_AND_JOB_NOT_EVALUATED | Не проверены конкретная новость, grant, job и сохранённый результат |
| REQUEST | EXECUTION_PREREQUISITES_NOT_EVALUATED | Общая возможность выполнения ещё не установлена; резервный UNKNOWN, не обещание будущего разрешения |
| IMPLEMENTATION | ADMINISTRATIVE_RETRY_ONLY | Нет публичного retry endpoint; GET ничего не разрешает |
| PROVIDER | PROVIDER_NOT_PROBED | Нет сетевой или платной проверки провайдера |

Все известные блокировки analyze_new перечисляются вместе. Например, у
read-only участника в demo будут ACCESS + MODE + DATA_POLICY. У full-пользователя
с can_analyze — DATA_POLICY для analyze_new и REQUEST/UNKNOWN для reuse_completed.
Порядок reasons не следует использовать как бизнес-правило клиента.

## HTTP-ошибки и ограничения

- **401 AUTHENTICATION_REQUIRED**: нет токена, он повреждён, истёк/отозван либо
  пользователь неактивен. `WWW-Authenticate: Bearer`. Без токена 401 даже без БД.
- **403 ACCESS_DENIED**: нет membership. Несуществующая и чужая компания дают
  одинаковый ответ; нет списка чужих компаний, ID новостей/заданий или counts.
- **422**: неверные path-параметры, стандартная FastAPI validation schema.
- **503 DATABASE_UNAVAILABLE**: нельзя проверить сессию/права/прочитать БД;
  нет анонимного fallback, DSN/SQL/сырого исключения в ответе.
- При известном запрете AI **сам capabilities GET возвращает 200** с BLOCKED,
  а не 503. Неизвестность провайдера также возвращается в теле 200.

Форма ошибки существующая: `{"detail":{"code":"...","message":"..."}}`.
Query `company_id`, `source_id` или `can_analyze` не меняет scope/права: целевая
компания берётся из path, пользователь — из сессии. Дополнительные query-поля
FastAPI игнорирует. Никакого клиентского user_id/права доступа API не принимает.

Capabilities — совет на момент запроса, не capability-token. Каждый последующий
endpoint независимо повторяет свои auth/membership/news grant проверки. Отзыв
прав или изменение состояния между запросами может изменить результат операции.
Ни один вывод capabilities не разрешает читать чужой COMPLETED cache. В full
RUNNING/FAILED/COMPLETED конкретных jobs не отражаются и не различаются в ответе.

## Переиспользование и совместимость

- `api/auth.py` и `AuthRepository.company_allowed` используются для ACL;
  сервис повторно проверяет membership и can_analyze тем же репозиторием.
- `settings.ai_disabled_reason` — единый mode reason для прежнего
  `api.runtime.require_ai_enabled` и capabilities, поведение demo не изменено.
- `external_transfer_guard` вызван с пустым non-None marker, поскольку company
  analysis требует non-None DB-контекст. Реальный контекст не загружается и не
  передаётся. Код/поведение guard не изменены.
- Jobs, attempts, retry policy, history, persistence и news grants не изменены;
  capabilities не запрашивает их таблицы. Не загружает PDF/CSV/RAG, не вызывает SDK.
- Новых миграций нет. Успешные существующие JSON и HTTP-коды сохранены.
  OpenAPI сообщает v1.22.1 и 15 операций; добавлены описания auth-ошибок,
  приватного дубликата, недоступной карточки и ограничений COMPLETED в demo.

Frontend не изменён. Для вызова нужен настоящий Bearer: прежний demo-login
по-прежнему несовместим. По отдельному согласованию обновлён `docker/smoke.py`:
проверяются конкретные path/method/security/ответы, а не число путей. Пропажа
capabilities, подмена метода или отсутствие ACL/503 проваливает проверку; новые
маршруты допускаются. Анонимный GET capabilities обязан вернуть 401.

Для дополнительной авторизованной HTTP-проверки передать в процесс smoke
`SMOKE_ACCESS_TOKEN` индивидуальной синтетической сессии, `SMOKE_COMPANY_SOURCE_ID`
своей и `SMOKE_FORBIDDEN_COMPANY_SOURCE_ID` недоступной компании. Токен — только
в памяти/env, не в аргументах/Compose-файле/Git. Проверяются 200, no-store, demo
BLOCKED и PROVIDER_NOT_PROBED, затем 403 чужой компании. Скрипт не создаёт
аккаунты, не вызывает AI и не использует общий токен. Без токена эта дополнительная
часть явно помечается SKIP, а анонимная ACL-проверка всё равно выполняется.

## Проверки и локальный проверочный файл

Unit/API-тесты: demo/full, can_analyze, категории причин, UNKNOWN провайдера,
неизменённый guard, безопасный 503 и защищённый OpenAPI. PostgreSQL-тесты:
READ ONLY транзакции, отсутствие новых news/jobs/attempts/analyses/evidence,
отзыв сессии/membership, подмена компании, отсутствие выдачи чужого cache,
одинаковый ответ capabilities при RUNNING/FAILED/COMPLETED, сохранение попыток.
Использованы только синтетические данные, fake analyzer и изолированная PG.

Результаты: профильный прогон **88 passed**, полный безопасный прогон
**847 passed, 0 skipped, 157,72 с**. В обоих случаях `BASELINE_PRESERVED`,
остановлен только свой PostgreSQL project; том и существующая external-сеть
сохранены. После финального уточнения текстов OpenAPI повторены unit/API/контрактные
тесты: **46 passed, 1,24 с**; runtime-логика после полного прогона не менялась.

Завершение версии: повторный профильный прогон вместе с пятью тестами обновлённого
smoke — **93 passed, 0 skipped, 24,34 с**, BASELINE_PRESERVED. Реальный HTTP-smoke
текущего backend в Docker успешен, включая авторизованные capabilities и 403 чужой
компании. Новая изолированная БД/project `pulse-caps-v1221-298850edd9`, новый том
`pulse-caps-v1221-298850edd9_data`, существующая сеть
`theyabliki-db-check-1a832d244c5f_default`. Свои контейнеры остановлены, том/сеть
сохранены; frontend demo и общая БД не использованы.

Образ `pulse-capabilities-v1221-check:20261025` собран из текущих исходников через
временный Dockerfile с библиотеками локального v1.22.0-образа; pinned requirements
и pip check прошли. Это не полная повторная загрузка всех зависимостей из сети.
Image ID `sha256:020a37c9a06c3f759779ed1b385b1dacb62aacf1dfba64097435b5d9e0b78ccd`.
Локальный безопасный итог: `C:/Users/nasty/AppData/Local/Temp/pulse-auth-docker-w5hv1uu9/result.json`.
SDK заблокирован, LLM env пусты; реальные данные не монтировались.

`backend/data/auth_check/run.py` прочитан целиком: встроенных паролей/API-ключей,
реальных CSV/PDF или записей набора не обнаружено. Случайные пароли генерируются
при запуске и передаются через память/env; путь/ID локальной сети и теги образов
являются временными настройками стенда, не credentials. Скрипт не запускался,
не редактировался, не добавлялся в Git и остаётся ignored. Его numeric OpenAPI
assert и version относятся к v1.22.0; автоматически использовать его для новой
версии нельзя. Существующие три незакоммиченных документа сохранены без изменений.

PREPARATION_FAILED остаётся нерешённым диагностическим вопросом; этот read-only
срез не изменяет подготовку анализа и не объявляет её исправленной.

## Изменённые файлы этого среза

Новые:

- `backend/api/capabilities.py`
- `backend/schemas/capabilities.py`
- `backend/services/capabilities_service.py`
- `backend/tests/test_auth_capabilities_unit.py`
- `backend/tests/test_auth_capabilities_integration.py`
- `backend/tests/test_auth_docker_smoke.py`
- `docs/CAPABILITIES_API.md`

Обновлены:

- `backend/main.py` — подключение router и version 1.22.1;
- `backend/settings.py`, `backend/api/runtime.py` — общий reason demo policy;
- `backend/api/auth.py`, `backend/api/company_analyses.py`,
  `backend/api/insights.py`, `backend/api/news.py` — только OpenAPI metadata;
- `backend/tests/test_auth_unit.py`, `backend/tests/test_news_matching_admin.py`,
  `backend/tests/test_openapi_contract.py` — 15 операций и уточнённые описания;
- `docs/API_CONTRACT.md` — новый endpoint и уточнение security-контракта.
- `docker/smoke.py` — согласованное обновление конкретных HTTP/OpenAPI проверок.

Всего 19 новых/изменённых файлов. Прежние незакоммиченные документы и ignored
локальные проверочные скрипты в этот список не включены. Push не выполняется.
