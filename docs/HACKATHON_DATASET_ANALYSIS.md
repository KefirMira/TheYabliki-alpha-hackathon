# v1.27.0: разрешённый dataset-путь анализа

## Граница разрешения

Основание — прямое сообщение разработчика проекта: организаторы разрешили
для разработки передавать необходимые данные предоставленного обезличенного
датасета в выданный LLM API. Это не разрешение на другие PostgreSQL-профили,
произвольные документы, персональные сведения, другие провайдеры или production.

Старый COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED сохранён без изменений.
Обычные company analyses и legacy AI endpoints не получают обхода.
ExternalContextPolicy v1.26.0 остаётся fake-only. HackathonDatasetPolicy —
отдельное прикладное исключение на фиксированную схему данных/цель/provider.

По умолчанию DATASET_AI_TRANSPORT=off. Fake и organizer выбираются только
оператором на сервере; клиент не может выбрать произвольный URL/модель/SDK.
Реальных LLM-вызовов при разработке v1.27.0 не выполнялось.

## Поток

React: выбранная компания -> ввод или тематический выбор сохранённой новости
-> подтверждение права передачи текста -> POST /api/news (если новости ещё нет)
-> POST /api/companies/{source_id}/news/{news_id}/dataset-analyses
-> ACL -> существующий atomic claim -> проверенный CSV snapshot
-> минимизация + локальный RAG -> live ACL -> один draft
-> strict JSON + provenance + financial review
-> существующая транзакция insight/evidence/cache/trace/COMPLETED -> лента.

Во время SDK-вызова соединение PostgreSQL не удерживается.
Используются CompanyAnalysisService, NewsAnalysisJobRepository, attempts,
CompanyAnalysisRepository, EvidenceRepository, PersistableAnalysis и прежняя
retry policy. Новых очередей и миграций нет.
Релевантность новости для компании — аналитический вывод, не подтверждённое
совпадение компаний из company matching.

## Какие поля могут передаваться

Только значения из current.attributes исходного CSV, а не произвольные
редактируемые companies.industry/revenue/name. Проверяются:
- источник df_Uid_data_hack;
- hash файла;
- SHA-256 канонической исходной строки из локального разрешённого manifest;
- полный набор 24 ключей и прежние CSV type/range/enum/Decimal проверки;
- соответствие SYNTHETIC_U выбранному source_id (сам ID в prompt не передаётся).

Из них существующий build_context формирует:
- отрасль, ОКВЭД, регион;
- выручку с currency=null, unit=null, year=null;
- исходные диапазоны сотрудников, не точное число;
- клиентский статус;
- банковские/факторинговые/ВЭД признаки для темы ставки/кредитования/финансирования.

Флаги не доказывают наличие долга, обязательства, экспорта, направления ВЭД
или действующего договора. CSV-значения — утверждения источника, не
независимо подтверждённые актуальные факты.

Опционально, только для отдельно разрешённого payment_file_sha256:
число исходных входящих/исходящих строк и различных внешних контрагентов.
Включаются в prompt только для тем поставщиков/платежей/расчётов.
Точные повторы сохраняются в counts. Контрагенты могут не иметь профилей.
Самосвязь учитывается в обоих направлениях. Нет периода/полноты охвата.
Суммы, PAY_CNT, валюты, реквизиты и отдельные платёжные строки НЕ передаются.

Опционально, для разрешённого link_file_sha256 и темы связей/структуры:
число исходных F–U строк и число разных внешних F identifiers.
F не считается физическим лицом; роль, контроль, владение и причинность
не выводятся. RC_NAME, CITY_NAME и сами F identifiers не передаются.

Не передаются имена компаний/людей, ИНН/ОГРН, IDs, GROUP_ID, сырые source_data,
файлы/имена CSV, auth/session metadata, финансовые результаты из иных источников.
Агрегации используют фиксированное число запросов с ограничением company source_id
и разрешённого hash; нет N+1 по контрагентам. Benchmark на полном реальном наборе
пока не выполнялся; опубликованный размер/число rows не является измерением latency.

## Разрешение совокупности и происхождение RAG

Manifest подтверждает разрешение фиксированной комбинации приведённых типов
признаков с текстом новости и разрешёнными RAG-фрагментами.
Это явное операторское подтверждение combination_approved, а не автоматический
union отдельных полевых разрешений из v1.26.0 и не оценка риска реидентификации.
Это НЕ универсальный DLP или доказательство анонимности комбинации.

Manifest находится вне Git, pin DATASET_AI_MANIFEST_SHA256 проверяется при загрузке.
Изменённая строка/файл, другая компания, невалидный source или неизвестный hash —
отказ до коммита claim/до SDK. DTO выдаёт policy; перед SDK проверяются identity
экземпляра и digest. Copy/подмена DTO и synthetic fixture DTO не подходят.

Каждый разрешённый аналитический chunk в corpus имеет точные:
source, page, chunk_id, text, text_sha256, publisher(ALFA_BANK/SYNTHETIC),
format(PDF/TXT), date(string/null). Text не переписывается; top-3 выбираются
существующим search_chunks по новости. Без подходящих источников анализ отклоняется.
Имя PDF не является основанием банковской атрибуции: publisher/format в release
проверяет оператор по оригиналу. Наличие ID/слов не доказывает смысловую поддержку.

В source_snapshot сохраняется проверенная provenance, в evidence — точный текст.
Старые evidence и неизвестные publishers не меняются задним числом.
Факт новости, цитата банковского источника и вывод модели отображаются раздельно.
Для synthetic TXT не появляется позиция Альфа-Банка.

Manifest — доверенная конфигурация сервера. Изменение БД её администратором,
подмена исходного release оператором и злонамеренный Python-код не входят
в модель sandbox-защиты. Нужны организационный контроль и проверка оригиналов.

## Новость и prompt injection

Для каждого запроса обязательно news_external_transfer_confirmed=true:
пользователь подтверждает право передачи именно текста выбранной новости,
без секретов/персональных данных. Это не blanket-разрешение пользовательских PDF.
Есть ограничение 5000 UTF-8 bytes и консервативный отказ для email,
Bearer, типовых key-строк и длинных цифровых идентификаторов.
Проверка не гарантирует распознавание всех секретов и смысловых персональных данных.
Перед реальным smoke оператор должен вручную просмотреть точный DTO.

Системная инструкция отделена от JSON данных. Текст документа/новости не
получает роль system. Нет tools/function calling; ответ с tool_calls запрещён.
Произвольные tool loops/URL fetching/fallback не добавлены.
Prompt injection нельзя считать полностью решённой одними delimiters/regex:
полезность и правильность реальных выводов требуют отдельной оценки.

## API и состояния

- GET /api/companies/{source_id}/capabilities: additive dataset_analysis и
  dataset_transport. AVAILABLE означает право попробовать при условиях,
  а не успешную проверку конкретного snapshot/news/job/provider.
  analyze_new старого пути остаётся BLOCKED.
- GET /api/companies/{source_id}/dataset-news: до пяти тематических кандидатов
  из последних 50 новостей с news grant; без внешнего AI, matching не подтверждён.
- POST /api/companies/{source_id}/news/{news_id}/dataset-analyses
  body: { "news_external_transfer_confirmed": true }.
  201 — новый результат, 200 — COMPLETED cache; 401/403 — ACL;
  409 — RUNNING/FAILED/retry/history policy; 422 — invalid request;
  502/503 — AI/storage/config/policy/unknown outcome.
- DATASET_PATH_DISABLED / DATASET_POLICY_DENIED / DATASET_GATEWAY_NOT_READY /
  DATASET_REAL_PAIR_NOT_APPROVED — не повторять автоматически.
- GATEWAY_TIMEOUT_UNKNOWN / GATEWAY_REQUEST_UNKNOWN / GATEWAY_USAGE_UNKNOWN,
  quota/length/JSON/tool errors: только фиксированный код в analysis_runs.error_message.
  Никаких provider bodies, headers, tokens или исходного запрещённого контекста.
  После dispatch ошибка требует прежней административной проверки, без auto retry.

COMPLETED cache общий для той же пары: fake-результат не заменяется платным.
Для реального smoke нужна отдельная новая разрешённая новость; нельзя чистить
историю или подменять fake cache реальным ответом.
ACL и news grant проверяются до cache/claim и ещё раз перед SDK.
Полный trace успешного draft и financial_review сохраняются атомарно с insight.
При отказе/ошибке до persistence нет частичного COMPLETED/insight/evidence;
сохраняется прежний статус FAILED с безопасным кодом, но не полный draft trace.

## Лимиты и стоимость

Фиксированные основной URL https://changellenge.up.railway.app/v1 и модель
deepseek/deepseek-v4.1-flash. Никакого автоматического резервного шлюза.
Повторно используется SyntheticDraftAdapter: общий bounded SDK dispatch/usage/
JSON validation, отдельный DatasetDraftAdapter.verify_dto. Synthetic path по-прежнему
проверяет свои pinned fixtures и не принимает dataset DTO.
SDK max_retries=0, follow_redirects=False, trust_env=False.
Один draft на attempt; output<=2000 включая reasoning; SDK timeout=60 s,
service timeout=120 s. Предел входа — 8000 по консервативному UTF-8 bytes+512,
не точный tokenizer. Общая конфигурация не содержит USD-тарифов.

Дневные 500 рублей команды и reset 03:00 МСК — сведения организаторов из
предыдущего согласования. Централизованного учёта расходов/остатка квоты нет.
Локальные token/request/time limits НЕ гарантируют денежный предел.

Первый реальный smoke дополнительно требует:
DATASET_AI_REAL_CONFIRMED=one-bounded-draft-approved и
DATASET_AI_REAL_PAIR_SHA256=SHA256(source_id + LF + decimal news_id).
Другие пары отклоняются до создания SDK. Перед draft разрешена только attempt_no=1.
Даже административно разрешённая attempt_no=2 не отправляет второй real draft
через smoke-путь. Это не меняет общую retry policy.

## Подготовка и запуск

По умолчанию всё выключено. Не включать organizer до отдельного согласования.

Offline manifest (локальный Python с backend dependencies):
~~~powershell
$env:PYTHONPATH = (Resolve-Path backend).Path
python -B -m dataset_release --profiles "<local profiles CSV>" --corpus-release "<reviewed chunks JSON>" --review-reference "<local approval ref>" --approve-dataset-combination --output backend/data/dataset-ai/manifest.private.json
~~~
Для counts дополнительно --payment-file "<CSV>" и/или --link-file "<CSV>".
CLI не импортирует данные в БД, не отправляет HTTP, выводит только counts/hash.
Conflicting/invalid profiles не входят в список разрешённых row hashes.
Output только под backend/data и не перезаписывает существующий файл.
Не добавлять manifest/corpus release/CSV/credentials в Git.

Fake backend на изолированной тестовой PostgreSQL:
~~~powershell
$env:DATASET_AI_TRANSPORT = 'fake'
$env:DATASET_AI_MANIFEST = '<absolute path to private manifest>'
$env:DATASET_AI_MANIFEST_SHA256 = '<SHA-256 of exact manifest bytes>'
$env:PYTHON_DOTENV_DISABLED = '1'
$env:AI_MODE = 'demo'
python -B -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 58149
~~~
DATABASE_URL задаётся локально без вывода, synthetic user/memberships —
через существующее provisioning, без обхода пароля.
Docker image читает dataset services из COPY services; manifest требуется
отдельным read-only bind mount. Не монтировать в образ .env/CSV/real PDFs.
Offline manifest CLI является host-side инструментом, не добавлен в image allowlist.

Frontend:
~~~powershell
$env:VITE_BASE_API = ''
$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:58149'
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5175 --strictPort
~~~

Подготовка реального smoke — ТОЛЬКО PLAN:
~~~powershell
$env:PYTHONPATH = (Resolve-Path backend).Path
python -B -m dataset_smoke_plan --plan --expected-database "<test_database>" --company "<locally selected source_id>" --news-id <saved_news_id>
~~~
Нужны DATASET_PLAN_DATABASE_URL (только loopback/test_*), manifest env и
интерактивный Bearer из существующего login. Token не пишется в argv/отчёт.
План повторно проверяет live ACL, формирует тот же DTO, не создаёт jobs
или SDK client. Выводит hash DTO/pair, source count, byte allowance, лимиты,
requests=0 и неизвестную стоимость. Для денежного согласования нет вымышленных цен.

После отдельного подтверждения оператор задаёт full/organizer, ключ только
в локальном окружении, оба real-smoke подтверждения и утверждённый manifest.
Один POST указанного выше dataset endpoint с Bearer и consent.
Эти настройки СЕЙЧАС не включены. Реальная отправка в этой задаче не выполнена.

## Проверенное окружение

Отдельная БД test_dataset_v127_20261025 в ранее созданном собственном тестовом
PostgreSQL project pulse-saved-pilot-20261025, loopback 58148; synthetic CSV/profile.
Существующие saved-pilot/integration-demo базы не изменялись.
Backend http://127.0.0.1:58149/docs, frontend http://127.0.0.1:5175.
Локальный synthetic login dataset-demo; пароль только
backend/data/dataset_ai_check/credentials.private.json (ignored).
Runtime PID и приватные параметры — в той же ignored директории.
Останавливать только PID своего backend/frontend после проверки CommandLine;
тома/сети/чужие процессы не удалять.

В браузере: login -> компания -> новость -> consent -> fake analysis -> feed -> card.
В карточке явная надпись «Локальная заглушка — LLM не вызывалась»,
UNKNOWN reviewer и точный TXT; отсутствующая позиция банка не выдумана.
Console warn/error=[].
16 HTTP-проверок: health/ready, auth/me/profile/feed/card, повтор COMPLETED,
invalid consent, 401/403, legacy denial, старый guard, candidates, logout204/revocation.
Read-only plan synthetic DTO: 6805 bytes allowance, requests=0; это не оценка
входа реального выбранного профиля и не гарантия его цены.

## Ограничения и критерий следующего шага

Техническая связность с fake подтверждена, качество настоящего вывода этим
не измерено. Требуются просмотр конкретной пары/DTO и release RAG по оригиналам,
проверка актуальности CSV snapshot и отдельное разрешение одного платного запроса.
Полный реальный dataset benchmark, новая Docker source build и реальный
провайдер в v1.27.0 не проверялись. Нет RSS automation, background bulk AI,
автоматического retry или новых financial truth claims.
Полный источник/позиция банка и смысловая поддержка выводов — разные проверки;
reviewer UNKNOWN/NEEDS_REVIEW не превращаются в PASSED.

## Полный состав изменений v1.27.0

- backend/main.py
- backend/repositories/company_analysis_repository.py
- backend/schemas/capabilities.py
- backend/schemas/orchestration.py
- backend/schemas/persisted_analysis.py
- backend/services/capabilities_service.py
- backend/services/company_analysis_service.py
- backend/services/synthetic_draft_adapter.py
- backend/tests/test_auth_unit.py
- backend/tests/test_news_matching_admin.py
- backend/tests/test_openapi_contract.py
- frontend/src/hooks/useCompanyCapabilities.ts
- frontend/src/pages/AnalyzeNews.test.tsx
- frontend/src/pages/AnalyzeNews.tsx
- frontend/src/pages/Insight.tsx
- frontend/src/shared/api/mappers/pulseMappers.test.ts
- frontend/src/shared/api/mappers/pulseMappers.ts
- frontend/src/shared/api/news.api.ts
- frontend/src/store/models/IPulse.ts
- frontend/src/store/service/Insights/runAnalysis.ts
- backend/api/dataset_analyses.py
- backend/dataset_release.py
- backend/dataset_smoke_plan.py
- backend/services/dataset_analysis.py
- backend/services/dataset_smoke_plan.py
- backend/tests/dataset_fixture.py
- backend/tests/test_auth_dataset_analysis.py
- backend/tests/test_dataset_policy.py
- docs/HACKATHON_DATASET_ANALYSIS.md

Шесть прежних EOL-only путей не входят в этот список и сохраняются без изменения frozen bytes.


## Итоговые проверки

- Полная backend-регрессия финального кода: 946 passed, 0 skipped, 266,82 с,
  включая PostgreSQL integration; failures/errors=0 по JUnit.
- Frontend: 141 passed в 29 файлах; TypeScript, production build (4,28 с),
  ESLint изменённых TS/TSX и Prettier пройдены.
- 16 реальных HTTP-проверок финального fake backend; браузерный E2E и
  тематический выбор сохранённой новости -> COMPLETED cache без нового draft.
- 8 конкурентных вызовов -> 1 attempt/1 draft/1 insight; без DB connection
  во время transport; rollback при evidence failure; timeout/quota/length/
  пустом/невалидном JSON/usage/tool_call errors нет повторов.
- Предварительный план: 6805-byte allowance для выдуманного профиля,
  source_count=1, requests=0. Точный реальный DTO ещё предстоит согласовать.
- COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED и v1.26 fake-only policy неизменны,
  существующие frozen rules/holdout SHA-256 совпадают, 46 исходных
  документов/артефактов сохранены.
- git diff --check и скан новых/изменённых файлов на локальные private values
  пройдены; секреты, CSV/PDF, manifest, SQLite, runtime logs не входят в diff.
- Ветка integration/frontend-backend, HEAD остаётся 8cb6fadcedc3a4844c49dc129646f53c5e7672f6.
  Ничего не staged/committed; push/merge/rebase не выполнялись.

Первый полный прогон обнаружил и помог исправить ранний импорт AI-модулей.
Контракты OpenAPI теперь проверяются точными маршрутами, а не только числом.
Новое API документировано, существующие HTTP-ответы анализа сохранены.
Это не доказательство качества настоящего LLM-анализа или безопасности
от всех видов prompt injection.

Предлагаемый коммит (не создан):

feat(analysis): подключить разрешённый анализ датасета к интерфейсу

Ограниченный DTO и release policy, существующие jobs и ACL,
проверяемые источники, reviewer и fake-проверка сквозного сценария.

Версия: v1.27.0
