# v1.24.0: синтетический контур SDK

Подготовлен внутренний сервис; новый endpoint, автоматический запуск и платные запросы не добавлены. По умолчанию используется инъекция локального fake-клиента. Обычный анализ компании по данным PostgreSQL остаётся под `COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED`.

## Поток и происхождение данных

1. `SyntheticGatewayExecutionService` наследует существующий локальный исполнитель. Сохраняются проверка действующей сессии, actor scope, доступ к компании/новости до claim/cache, существующие jobs и fenced commit. Целевая БД должна быть loopback PostgreSQL с именем `test_news_identity_<32 hex>`; source_id фиксирован fixture-набором. Production/demo/import БД не подходят.
2. `AnalysisPreparationService` читает снимок локально и по-прежнему получает BLOCKED от guard для DB-контекста. Этот снимок наружу не передаётся. В gateway-отчёт полный preparation не включается.
3. Для внешнего профиля, планирования и financial review используется отдельный фиксированный контекст `backend/fixtures/gateway_macro_v1.json`: синтетическая новость о ставке, вымышленное производство оборудования, признак кредитного продукта и два учебных аналитических фрагмента. Неизвестные условия займа остаются неизвестными. Это не реальные данные и не финансовые рекомендации.
4. Файл читается только по встроенному пути. SHA-256 канонического JSON закреплён в `synthetic_gateway_input.py`: `e69222b04f5a2fbabf651d258efd173bf522a39f96b5b57eed15d32b8e685dc0`. Нормализация JSON делает проверку независимой от CRLF/LF. Изменение набора требует review и явного обновления pin; вызывающий код не задаёт путь или ожидаемый хеш.
5. `make_input(chunk_ids)` принимает только идентификаторы разрешённых фрагментов, а не профиль или произвольный текст. Frozen DTO с `extra=forbid` содержит сообщения, заново собранные из проверенного набора. `evidence_ids` сопоставляет документ/страницу/chunk/text/date с corpus; DB-новость должна дословно соответствовать fixture. Названия, дополнительные поля и платежные данные БД в DTO не копируются.
6. `SyntheticDraftAdapter.complete` вызывает `verify_input` до резервирования единственного SDK dispatch и повторно непосредственно перед `create`. Проверка пересобирает ожидаемый DTO и сравнивает всё содержимое. Одного поля `synthetic=true`, правильного имени компании или заявленного хеша недостаточно.

Локально существующий personalization assembler ещё формирует question с DB-контекстом. Новый draft provider намеренно не читает/не отправляет это поле: SDK получает только сообщения из synthetic DTO. Оригинальный `_ai_context` компании не обнуляется, guard не отключается. SQL, DB ids, source_data, реальные CSV/PDF и auth/session credentials в сообщения не включаются.

## SDK и ограничения

`SyntheticDraftAdapter(fake_client)` не импортирует OpenAI SDK, не читает API-ключ и не выбирает конфигурацию из `.env`. Тестовый клиент записывает вызовы в память и возвращает локальный JSON.

Подготовлена, но не выполнялась с настоящим SDK, фабрика `organizer(...)`. Для неё одновременно нужны явные `allow_real=True`, `acknowledge_unknown_cost=True`, переданный credential, действующий `AI_MODE=full`, точные основной URL и модель. Политика demo повторно проверяется непосредственно перед dispatch; одной проверки при создании клиента недостаточно. В проекте нет нового API/CLI, автоматически вызывающего эту фабрику.

| Ограничение | Значение |
|---|---|
| SDK dispatch | Не более одного за жизненный цикл adapter instance |
| Input allowance | По умолчанию 8000; нельзя увеличить выше 8000 |
| Output | По умолчанию 1000; явный предел не выше 2000, включая reasoning |
| SDK timeout | По умолчанию 60 секунд, нельзя выше 60 |
| Общий срок исполнения | 120 секунд, внутри прежнего protected timeout 150 и lease 180 |
| Provider | Только `https://changellenge.up.railway.app/v1` |
| Model | Только `deepseek/deepseek-v4.1-flash` |
| Retries/fallback | 0; резервный URL не используется |
| HTTP transport | TLS defaults, redirects=False, trust_env=False |
| Planner | Прежний локальный deterministic fake planner; без платных решений |
| Tools | Прежний allowlist, максимум 3 решения, 1 draft, 1 допоиск, 1 локальная корректировка и 2 проверки |

Вход ограничивается UTF-8 byte planning bound с дополнительным allowance 512, не проверенным tokenizer этой модели. Для двух фрагментов текущего набора bound — 3683. Returned usage дополнительно проверяется на типы, непротиворечивость и configured ceilings; превышение обнаруживается после ответа и не отменяет возможное списание. Не заявляется строгая провайдерская гарантия входного token count или денежного лимита.

Общий денежный бюджет команды централизованно не учитывается. Ограничение одного adapter instance не координирует другие процессы, ключи и участников. Pair-level jobs защищают повтор одной пары, а не глобальный бюджет. Любой настоящий запуск по-прежнему требует отдельного разрешения пользователя; новые экземпляры adapter не являются способом автоматического retry.

## Результат, ошибки и самопроверка

- Принимается один выбор с finish_reason=stop, непустым JSON и валидным usage. `length`, пустой ответ, отсутствие usage, tool/function calls, лишние/дублированные JSON-поля и несоответствие обязательной схеме отклоняются. Локального обрезания ответа или генеративного repair нет.
- Используются прежние JSON assembly, exact provenance, финансовая проверка и консервативное удаление целого пункта по прежнему allowlist. После удаления повторяются structural/provenance/financial checks. Модель не может выбрать произвольный инструмент или выполнить код.
- Summary/рекомендации остаются синтетическими модельными предположениями, `validation.passed=false`, финансовая корректность UNKNOWN, human review required. Наличие источника не доказывает смысловую поддержку утверждения. Residual S01/S02 reviewer и исторический PREPARATION_FAILED этим срезом не исправлены.
- Timeout, сетевой сбой и отмена могут означать неизвестный исход у провайдера. Никаких автоматических повторов. После dispatch прежний механизм фиксирует FAILED + REVIEW_REQUIRED; если подтверждение статуса потеряно — UNCERTAIN. Истечение lease не разрешает новый запрос.
- Если результат commit уже сохранён, потеря подтверждения не вызывает второй SDK dispatch: читается COMPLETED cache. Закрытая администратором попытка отклоняет поздний ответ через claim-token/owner fencing.
- Чужой cache не раскрывается: ACL выполняется раньше. Существующий fake COMPLETED также не заменяется реальным вызовом и не выдаётся за доказательство real inference. Подготовку нового отдельно согласованного синтетического пилота нельзя превращать в автоматическую смену cache key.

## Trace и атомарность

Старый `OrchestrationTrace` сохраняет `paid_calls=0`. Новый `GatewayOrchestrationTrace` имеет отдельную версию, transport, sdk_requests, paid_calls, outbound SHA-256, allowlisted usage/reasoning_tokens, finish_reason, elapsed_ms, outcome и безопасный error_code. План, решения, инструменты, хеши и проверки используют прежнюю структуру событий.

`paid_calls` для organizer означает консервативный счётчик инициированных SDK dispatch, а не доказанное число списаний. В fake transport он равен нулю, даже если тесты проверяют один SDK-shaped вызов. В отдельном тесте organizer-фабрика подменена локальным fake SDK: это проверка accounting, не реальный платный запрос.

Не сохраняются ключ, authorization headers, exception repr, сырой SDK object, скрытый reasoning или сообщения с DB-контекстом. Полный failed trace остаётся в памяти; в analysis_runs сохраняется прежний безопасный фазовый код. Гибель процесса может потерять подробный failed trace — crash-safe журнал требует отдельного согласования схемы. CHECK на attempts.response_payload и строгие сигнатуры миграций не обходятся.

Успешный trace сохраняется в `validation.orchestration` той же транзакцией, что insight, evidence, response payload и COMPLETED. Ошибка записи trace или evidence откатывает весь результат; не создаётся фиктивный insight ради failed trace. Новых таблиц/миграций нет.

## Проверки и Docker

Профиль: **108 passed, 0 skipped**, 63,93 секунды. После финального уточнения названий событий выполнена полная регрессия из корневого pytest.ini: **1001 passed, 0 skipped**, 257,80 секунды (backend + parser, включая PostgreSQL integration). Предшествующий отдельный backend-прогон: 841 passed, 0 skipped, 252,31 секунды. Тесты используют только синтетические данные, fake SDK и UUID PostgreSQL databases в ранее проверенном отдельном Compose project. Внешние socket connections и случайный import реального SDK блокируются runner/conftest.

Baseline fingerprint БД до/после совпал. Остановлен только project `theyabliki-orchestration-518a9e2e9d75`; том и сеть сохранены. `git diff --check` прошёл; в 14 файлах среза нет trailing whitespace и совпадений проверенных шаблонов private key/Bearer/API-токенов. Семь прежних документов совпали по SHA-256. HEAD остаётся `c510b890ab10feed5cb98399dbc5a29ed3ed1885`, staging пуст, коммита нет.

Первый unit-запуск внутри Windows sandbox завис на asyncio; остановлен только его pytest-процесс, проверки продолжены вне sandbox. Найденные в разработке ошибки Literal[1]/bool и соответствия `source`/`document` исправлены и покрыты тестами. Зависших тестовых команд на момент завершения нет.

Проверены: DTO tampering/manifest/source IDs; токены/time/request limits; demo и повторная mode-проверка; JSON/usage/length/empty/network/quota/timeout; безопасные ошибки; отсутствие соединения БД во время SDK; 8 конкурентов; ACL до cache; guard; исправление с повторной проверкой; поздний ответ; потеря commit acknowledgement; rollback trace/evidence; прежние API и jobs/retry.

В Dockerfile и `.dockerignore` добавлен только конкретный synthetic fixture. Compose, frontend demo и миграции не изменены. Полная offline-сборка исходного Dockerfile остановилась на pip: wheel `annotated-doc==0.0.5` отсутствует в кеше, сеть отключена. Проверочная сборка текущих исходников выполнена поверх локального `pulse-capabilities-v1221-check:20261025` с ранее установленными зависимостями; это не чистая переустановка dependencies.

Docker smoke: собственный одноразовый контейнер, `--network none`, read-only filesystem, cap-drop ALL; fixture pin, fake SDK, импорт сервиса, ASGI HTTP /health, /docs, /openapi.json — 200; /api/me и capabilities без авторизации — 401; новых gateway routes нет. Реальный openai import заблокирован. Контейнер удалён после завершения, чужие ресурсы и тома не затронуты. Этот smoke не является HTTP E2E с PostgreSQL в Docker; SQL/ACL/persistence отдельно покрыты PostgreSQL integration.

## Файлы v1.24.0

- `backend/fixtures/gateway_macro_v1.json`.
- `backend/services/synthetic_gateway_input.py`, `synthetic_draft_adapter.py`, `synthetic_gateway_execution_service.py`.
- `backend/services/synthetic_news_execution_service.py`: небольшие hooks для повторного использования существующего lifecycle, сохранён fake-only контракт старого входа.
- `backend/schemas/orchestration.py`, `persisted_analysis.py`, `synthetic_execution.py`: отдельные внутренние gateway contracts, без смены HTTP responses.
- `backend/tests/synthetic_gateway_fixture.py`, `test_synthetic_gateway_unit.py`, `test_auth_synthetic_gateway_integration.py`.
- `backend/Dockerfile`, `backend/.dockerignore`.
- Этот документ. Семь прежних незакоммиченных документов не редактируются.

Предлагаемый коммит после просмотра и успешных проверок:

```text
feat(analysis): подготовить безопасный синтетический контур LLM

Проверяемый fixture DTO, ограниченный SDK draft и атомарный trace
через существующие jobs без ослабления запрета передачи DB-контекста.

Версия: v1.24.0
```

Коммит и публикация не выполнялись. Реальных LLM-запросов — 0.
