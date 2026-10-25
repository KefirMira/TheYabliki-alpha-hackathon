# Локальный адаптивный анализ — v1.23.0

Это ограниченный контроллер с детерминированным fake planner, а не автономный LLM-агент.
Он действительно выбирает инструменты по наблюдениям и пересматривает оставшийся план,
но качество рассуждений модели этим не проверяется. Сетевых вызовов нет.
Production endpoints, промпты и `COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED` не изменены.

## Переиспользованные компоненты

`SyntheticNewsExecutionService` остаётся единственной внутренней точкой исполнения.
`CompanyAnalysisService` проверяет company/news ACL, выполняет существующие claim/dispatch,
возвращает COMPLETED cache и сохраняет результат с fencing. Jobs, attempts и retry policy
не заменены. `AnalysisPreparationService` читает согласованный снимок, строит company context,
выполняет baseline RAG и проверяет запрет внешней передачи. Использованы прежние
`search_chunks`, personalization/parser, `PersistableAnalysis` и финансовый reviewer.

Сессия PostgreSQL закрыта до planner, draft и дополнительного RAG. Корпус фиксируется
один раз на исполнение; baseline и дополнительный поиск используют тот же снимок.
Тексты найденных фрагментов должны точно принадлежать этому корпусу. Это проверка
происхождения, а не доказательство того, что источник подтверждает финансовый вывод.

## Actor scope

Конструктор внутреннего сервиса принимает `session_token: str | None`; токен хранится
в `SecretStr`. Перед каждым `analyze_saved` вызывается настоящий `AuthService.authenticate`.
Полученный сервером `user_id` передаётся в существующий `CompanyAnalysisService`.
Действующая индивидуальная сессия, membership с `can_analyze` и news grant обязательны
даже перед возвратом кеша. Передать произвольный actor UUID вместо сессии нельзя.
Ошибки возвращаются во внутреннем отчёте как REJECTED с существующими кодами
`AUTHENTICATION_REQUIRED`/`ACCESS_DENIED`; новый HTTP endpoint не добавлен.

Дополнительно остаётся прежний барьер: явное `confirm_synthetic=True`, SYNTH-prefixed
компания, loopback asyncpg и база `test_news_identity_<32 hex>`. Это разрешение только
для тестовых UUID-баз; frontend demo, импортированные реальные данные и общая БД не подходят.
Тестовые токены создаются индивидуально и хранятся в БД только как хеши.

## Наблюдения и реальные ветви

| Наблюдение | Решение и действие |
|---|---|
| Нет baseline-фрагментов | STOP до fake draft, FAILED по существующему механизму |
| Неизвестны industry и okved_code либо найден только один источник | Один дополнительный локальный SEARCH_RAG |
| После допоиска есть источники | Новое наблюдение и решение DRAFT; повторный допоиск запрещён |
| Контекст содержит industry/okved_code и есть минимум два источника | DRAFT сразу |
| Финансовая проверка вернула blocker | STOP; COMPLETED не сохраняется, даже если planner предложил KEEP |
| Есть корректируемый NEEDS_REVIEW для пункта risks/opportunities/recommendations | Удаление одного целого пункта и повторная проверка |
| Остались UNKNOWN/NEEDS_REVIEW без blocker | Сохранение с предупреждениями и обязательной экспертной проверкой |

Planner получает только типизированное наблюдение: число отсутствующих полей, признак
неполноты профиля, число источников, факт допоиска, blocker, коды findings и допустимые
поля для удаления. Он не получает токен, SQL, произвольные URL или возможность менять
company_id/news_id. Аргументы дополнительного поиска строит контроллер из разрешённого
профиля и новости, максимум 2000 символов; используется прежний top_k=3, общий максимум
6 фрагментов и прежний MAX_INPUT_BYTES. Частотный score не считается уверенностью.

Решение — строгая Pydantic-схема с запретом дополнительных полей и allowlist действий.
Для каждой фазы проверяется отдельный allowlist. Неизвестный инструмент, неверная фаза
или поле корректировки вне текущих findings останавливают исполнение.

## Корректировка и самопроверка

Автоматически удаляется только **один целый элемент списка**, отмеченный NEEDS_REVIEW
одним из кодов CORRECTABLE в `local_adaptive_service.py`. Summary автоматически не
переписывается. Новый факт, число или источник взамен не генерируются; это консервативное
изъятие неподтверждённого пункта, а не доказательство его ложности.

Повторная сборка идёт через прежний parser без второго SDK-вызова. Затем вновь проверяются:
JSON/Pydantic-контракт, company/news identity, точное evidence и финансовые утверждения.
Любая ошибка или blocker препятствует сохранению. После одной корректировки оставшиеся
сомнительные выводы сохраняются только как требующие экспертной проверки.
`validation.passed` принудительно false в этом синтетическом режиме; финансовая корректность
всегда UNKNOWN. Пустой список предупреждений не превращается в сертификат достоверности.

## Жёсткие лимиты

- 3 decision calls, 1 fake draft, 1 дополнительный RAG, 1 корректировка, 2 review-цикла.
- 0 реальных LLM-запросов; никакого retries/fallback и новой очереди.
- 32 события, 16 KiB JSON журнала; переполнение останавливает исполнение.
- При отказе используются прежние FAILED/REVIEW_REQUIRED; автоматического retry нет.

## Атомарный журнал

`validation.orchestration` использует существующий JSONB `company_news_analyses.validation`.
Миграции не нужны. Репозиторий принимает только VALIDATED trace, получает checked-копию
COMPLETED с событием PERSIST и сохраняет её в той же транзакции, что insight, evidence,
response_payload и COMPLETED. Ошибка любой записи откатывает все эти объекты.

Журнал содержит исходный и оставшийся план, наблюдения, решения, выбранные инструменты,
хеши их результатов, source IDs, поле удаления, хеши до/после и итоговый статус.
В нём нет паролей/токенов, исходного company context, текста новости или финансовых сумм.
Полные исходные синтетические входы по-прежнему доступны во внутреннем preparation report.
При неуспехе trace остаётся в памяти отчёта со статусом FAILED; отдельного долговременного
журнала неуспешных попыток этот срез не создаёт. Кеш не запускает planner и не реконструирует
trace в отчёте; первоначальный журнал остаётся в сохранённой карточке insight.

Пример пути реально проверяемого сценария удаления (полный JSON генерируется тестом
`test_adaptive_paths_atomic_trace_cache_and_no_connection[repair]` в pytest tmp_path):

```text
PREPARE
OBSERVE: context_partial=false, source_count=2, source_support=UNKNOWN
DECIDE DRAFT → [DRAFT, VALIDATE, REVIEW, DECIDE, PERSIST]
DRAFT (fake, один вызов)
VALIDATE (schema + точное evidence)
REVIEW: FINANCIAL_NUMBER_NOT_IN_INPUT, COMPANY_CONTRACT_NUMBER_UNVERIFIED
DECIDE REMOVE_CLAIM risks[0] → [REMOVE_CLAIM, VALIDATE, REVIEW, PERSIST]
REMOVE_CLAIM: whole item removed, before_sha256 != after_sha256
VALIDATE (повторная проверка)
REVIEW (повторная проверка, финансовая корректность UNKNOWN)
KEEP_WITH_WARNINGS
PERSIST ATOMIC_COMMIT → COMPLETED
decisions=2, drafts=1, searches=0, corrections=1, reviews=2, paid_calls=0
```

## Изменённые файлы

- `backend/schemas/orchestration.py` — новый строгий контракт решений и журнала.
- `backend/services/local_adaptive_service.py` — новые локальные правила и bounded controller.
- `backend/services/synthetic_news_execution_service.py` — actor scope и интеграция.
- `backend/schemas/persisted_analysis.py`, `backend/schemas/synthetic_execution.py` — optional trace.
- `backend/repositories/company_analysis_repository.py` — атомарная запись trace в JSONB.
- `backend/tests/synthetic_actor_fixture.py` — индивидуальные синтетические сессии.
- `backend/tests/test_local_adaptive_unit.py` — решения, allowlist, лимиты и происхождение.
- `backend/tests/test_auth_adaptive_integration.py` — PostgreSQL ACL, ветви, исправление, rollback.
- `backend/tests/test_synthetic_execution_integration.py` — прежние jobs, concurrency, кеш с ACL.
- `backend/tests/test_financial_review_integration.py` — прежний reviewer с обязательной сессией.
- Этот документ. Четыре прежних незакоммиченных документа аудита не изменены.

## Ограничения и следующий этап

Релевантность пары компания/новость не установлена самим агентом: пара явно выбрана
пользователем с ACL. Наличие источника не доказывает entailment; это остаётся UNKNOWN.
Базовый fake draft намеренно не содержит финансовых выводов. Финансовые спорные случаи
подаются синтетическими тестами, а не получены от модели. Никакой автономной постановки
целей, произвольных инструментов или самоподтверждения нет.

Ранее наблюдавшийся неповторившийся PREPARATION_FAILED остаётся нерешённым диагностическим
вопросом. Успех текущих тестов не объявляет его исправленным. Возможный следующий срез —
более содержательный локальный relevance/coverage planner и явный безопасный контракт
долговременной диагностики неуспешных попыток, без автоматического подключения провайдера.

## Результаты проверок

Проверено 25 октября 2026: профильный прогон — 105 passed; после добавления трёх
дополнительных регрессионных кейсов полный финальный прогон backend + parser —
**885 passed, 0 skipped**, 158,75 секунды. Он включает PostgreSQL integration, восемь
конкурентных запусков, ACL до claim/cache, неизменность публичного OpenAPI, отсутствие
соединения БД во время fake SDK, ошибку записи evidence/trace, blocker после корректировки
и подмену evidence при повторной сборке. Fake SDK единственный; импорт внешнего SDK
блокируется conftest, сетевой guard runner разрешал только loopback.

Использован существующий изолированный Docker project
`theyabliki-orchestration-518a9e2e9d75` с собственным томом и проверенным override внешней
тестовой сети. Тесты создавали дочерние UUID-базы; baseline fingerprint до/после совпал.
Контейнер проекта остановлен, том и сеть сохранены. Общие/production/demo-БД не использованы.

Для повторения нужны тестовые зависимости и изолированная PostgreSQL с защитными DSN
из существующего `backend/tests/run-profile-tests.ps1`; новые тесты автоматически входят
в backend suite. Вручную заданный NEWS_IDENTITY_TEST_DATABASE_URL должен указывать только
на изолированный fixture baseline, никогда на импортированные реальные данные.

Полный HTTP-контракт не менялся. Отдельная Docker-сборка/HTTP-smoke этого внутреннего
среза не выполнялась. Коммит и публикация не выполнены.
