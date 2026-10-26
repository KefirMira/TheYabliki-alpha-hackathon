# Публичный saved-pilot demo — v1.28.0

Рекомендуемый автоматический Docker-запуск описан первым в README.
`docker compose -f compose.saved-pilot-demo.yml up --build -d --wait` создаёт
отдельную БД, запускает guarded offline seed с паролем из локального .env,
backend и nginx/frontend на 8082. Swagger на 8010. Аккаунт synthetic-pilot-viewer
имеет только чтение. Новых SDK-вызовов нет, источники учебные TXT.

Импортёр сохраняет исходные content/evidence/findings/trace. Режим --password-env
меняет только получение пароля; проверки marker, пустой БД, повторного snapshot,
закреплённых SHA-256 и транзакционность остаются прежними. Ниже — прежние сведения
о происхождении и ручной диагностике. Старые локальные порты/команды разработки
не являются актуальной инструкцией публичного автоматического запуска.

# Сохранённый синтетический LLM-пилот — v1.25.1

Изменения подготовки публичного запуска пока не закоммичены.
Исходные backend/frontend ветки и оригинальные артефакты не меняются.

## Что демонстрируется

Один фактический ответ DeepSeek от 25.10.2026 на утверждённый synthetic fixture.
Не новый запрос, не заранее написанная замена ответа и не анализ реальной компании.
Пять полей исходного JSON, 2 evidence, все 20 findings и исторический trace сохранены.
Reviewer: 16 UNKNOWN, 4 NEEDS_REVIEW, 0 CONFIRMED_ERROR.
Финансовая достоверность не подтверждена; JSON/provenance не доказывают её.

Исходный локальный отчёт: docs/LLM_FIRST_REAL_TEST.md в основной backend-копии.
Исходные файлы: backend/data/llm_first_real_test (исключены из Git).
В интеграционной копии используется проверяемый минимальный экспорт
backend/fixtures/saved_llm_pilot_v1.json. Он содержит только синтетические данные:
сырой content ответа, sources, validation/review/trace и allowlisted метаданные.
Там нет SQL ID, аккаунтов, Authorization, ключа, скрытого reasoning-текста,
DB-профиля, платежей, CSV или PDF. Оригинальные артефакты не копируются в image.

## Происхождение

- canonical SHA-256 экспорта:
  5c75a2d975712f20303c065adaf64d69337d1812cc6738aa49cc23a2c14a243f
- исходный execution.json:
  0412f586c596fa14b6dccdcfc6e1039203f673a955a87b01b646c6522df0dafc
- исходный provider-response.json:
  e8a1c603352a6466b8242b86cc6a563a19cef55e4dd52ea16ac794975d1fee46
- content ответа:
  f0d695ec9ad8d539b540470f0e92b657e0828a83cbfcecc3b50ada4db8091ef3
- утверждённый fixture:
  e69222b04f5a2fbabf651d258efd173bf522a39f96b5b57eed15d32b8e685dc0
- DTO:
  8b218f5f668e0874895b606644f462ce39fdd5fd55b3309e0a8597998f36fa55
- wire:
  49c03098313774e5c70237f9d442300022589306548c318e45d4aa608cdaed3a

Importer принимает только встроенный fixture с закреплённым canonical hash,
пересоздаёт DTO существующим make_input и проверяет его хеш. Произвольного пути
к произвольному JSON или флага synthetic=true для обхода проверки нет.
Изменённый content, источник, trace, findings или добавленный ключ приводят к отказу.
Обновлять pin для другого ответа без отдельного просмотра нельзя.

## БД и атомарность

Отдельный compose.saved-pilot-demo.yml, новая БД test_saved_pilot_demo,
отдельный новый том saved_pilot_pgdata и отдельный project.
Прежний integration_demo.py и integration_demo.sql не изменены.
Новый маркер только при init нового выделенного тома:
pulse:isolated-saved-pilot-demo:v1. Схема/миграции 001–007 не изменены.

В БД создаются:
- 1 компания SYNTH-GATEWAY-MACRO-A, только подтверждённые synthetic fixture факты;
- name=source_id как технический placeholder из-за NOT NULL. API возвращает
  name=null/name_is_placeholder=true; имя/ИНН/ОГРН/выручка не выдумываются;
- 1 приватная новость с исходным учебным текстом;
- 1 COMPLETED analysis_run, 1 insight, 2 DOCUMENT evidence;
- 1 Argon2id-аккаунт synthetic-pilot-viewer, membership can_analyze=false,
  grant только на эту новость;
- 0 jobs и 0 attempts: импорт не изображает новую платную попытку.

Используются прежние repositories в одной внешней транзакции и savepoint.
Уже COMPLETED trace не проходит повторный committed lifecycle; он сохраняется
точно как история в той же транзакции. Ошибка evidence/trace откатывает всё,
включая компании, аккаунт, run и grants. Новый orchestration lifecycle не создаётся.

Advisory transaction lock сериализует конкурентные импорты.
Первый запуск допускает только пустую БД. Повтор проверяет полный fingerprint
всех public-таблиц (кроме сессий и собственного checksum) и Argon2id-пароль.
Смена данных/прав/пароля — отказ без автоматического исправления.
Login/logout не нарушают идемпотентность. Повтор с тем же снимком — UNCHANGED.
После неопределённого commit оператор сначала проверяет состояние/повторный dry-run;
это offline-импорт, повторного SDK-вызова в нём нет.

## Права

Каждый API-запрос по-прежнему проверяет сессию и company/news ACL.
can_analyze=false запрещает анализ; legacy AI endpoints также не предоставляют обход.
Исправлен существовавший пробел POST /api/news: создание новости требует
хотя бы одного server membership с can_analyze=true, иначе ACCESS_DENIED 403.
Ранее там хватало любой действующей сессии. Это единственное уточнение прав
существующего endpoint; OpenAPI дополнен. Для пользователей с write membership
контракт записи и приватная дедупликация сохранены.
Сессия и logout остаются доступными: read-only относится к предметным данным,
а не запрету управлять собственной сессией.

COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED не менялся.
Importer не импортирует SDK, не создаёт адаптер и не подключает внешний gateway.
Demo-контейнеры имеют пустые LLM-переменные и AI_MODE=demo.

## Запуск нового стенда

Нужны Docker Desktop/Linux containers, Compose v2; frontend — Node.js 24/npm 11.
Из корня интеграционного worktree, в PowerShell:

~~~powershell
$env:SAVED_PILOT_DB_PASSWORD = [guid]::NewGuid().ToString('N')
$env:SAVED_PILOT_PORT = '8010'
docker compose -p pulse-saved-pilot-demo -f compose.saved-pilot-demo.yml build backend
docker compose -p pulse-saved-pilot-demo -f compose.saved-pilot-demo.yml up -d --wait postgres backend

# По умолчанию только PLAN_ONLY; никаких записей.
docker compose -p pulse-saved-pilot-demo -f compose.saved-pilot-demo.yml run --rm seed

# Явное применение; пароль нового viewer вводится через getpass дважды.
docker compose -p pulse-saved-pilot-demo -f compose.saved-pilot-demo.yml run --rm seed python -B -m saved_pilot_demo --expected-database test_saved_pilot_demo --apply --confirm-isolated
~~~

Повторите последнюю команду с тем же паролем: UNCHANGED.
Пароль PostgreSQL нужно сохранить локально безопасным способом и не менять для
уже существующего тома. Нельзя ставить маркер вручную в shared/production БД.
CLI требует loopback, явный порт, postgresql+asyncpg, test_*,
совпадение имени и свой маркер; URL-query отклоняется.
Seed использует namespace именно своего PostgreSQL: host-порт не требуется.

Frontend в другом терминале:

~~~powershell
$env:VITE_BASE_API = ''
$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:8010'
npm --prefix frontend ci
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5174 --strictPort
~~~

Открыть http://127.0.0.1:5174, login synthetic-pilot-viewer, пароль из getpass.
Доступна одна компания, один сохранённый инсайт; модель выключена.
Никакие реальные CSV/PDF/LLM ключи для запуска не требуются.
Production dist требует reverse proxy; Vite proxy относится только к dev.

## Проверенное окружение этого задания

Project pulse-saved-pilot-20261025, собственный том
pulse-saved-pilot-20261025_saved_pilot_pgdata.
Backend http://127.0.0.1:58147; Swagger /docs.
Frontend http://127.0.0.1:5174.
Отдельный тестовый loopback PostgreSQL-порт 58148 использован regression runner.
Использована ранее проверенная внешняя Docker test network с уникальным DNS
собственного PostgreSQL-контейнера; чужие проекты не изменялись.

Пароль viewer только в локальном ignored файле
backend/data/saved_pilot_demo_check/credentials.private.json.
DSN/параметры собственного project — environment.private.json; не печатать и не публиковать.
HTTP-результаты — http_report.json. Секреты не входят в исходники.
Проверочная сборка — свежие источники поверх ранее проверенного dependency image,
offline. Чистая загрузка зависимостей с registry не подтверждена.

Стандартную команду запуска нельзя бездумно применять к другому существующему
project/тому. Для перезапуска именно проверенного project прочитать локальные
SAVED_PILOT_DB_PASSWORD и SAVED_PILOT_PORT из environment.private.json без вывода
значений и использовать одновременно -f compose.saved-pilot-demo.yml и
-f backend/data/saved_pilot_demo_check/override.private.yml.

Остановка только своего проверочного project (после установки тех же env):

~~~powershell
docker compose -p pulse-saved-pilot-20261025 -f compose.saved-pilot-demo.yml -f backend/data/saved_pilot_demo_check/override.private.yml stop
~~~

Frontend вручную — Ctrl+C. Фоновый процесс: сверить PID из runtime.json и
CommandLine именно этого worktree/порта, затем остановить только этот процесс.
Тома и сети сохранять; prune/down -v запрещены.

## Отображение и ограничения

На всём выбранном pilot scope есть пометка «Синтетический пример».
На карточке — предупреждение, фактическая модель/дата пилота, время/usage,
отдельная дата импорта и исторический раскрываемый trace.
Reviewer показывает 16 UNKNOWN и 4 NEEDS_REVIEW, все 20 findings раскрываются.
Отсутствие confirmed errors не означает корректности.
Номера Источник 1/2 привязаны к двум исходным текстам; неизвестный publisher
не становится Альфа-Банком. Содержимое evidence и пяти полей модели не меняется.
Дата записи в feed обозначает импорт, а не повторную генерацию.

2395 токенов, включая 1452 reasoning внутри 1784 output, и 15,688 с — сведения
того одного исторического запуска. Валюта usage.cost неизвестна, денежная
оценка в интерфейс не переносилась. Командная квота сейчас не опрашивалась.

Reviewer может давать ложные срабатывания; оговорки и спорная поддержка ссылок
не исправлялись автоматически. Исторический PREPARATION_FAILED не объявляется
исправленным. Избранное/hide остаются локальными preferences браузера.

## Проверки

Полная backend-регрессия: 877 passed, 0 skipped (253,66 с), включая PostgreSQL integration.
Frontend: 139 passed, 0 skipped; TypeScript, production build, lint и форматирование изменённых TS/TSX прошли.
Уже проверены: dry-run → CREATED → UNCHANGED; 8 конкурентных импортов,
ACL разных пользователей, read-only POST, rollback evidence/trace и защита snapshot.
22 настоящие HTTP-проверки: health/ready/docs/OpenAPI, login/me/profile/feed/card,
401/403, legacy routes denied, CORS Authorization и logout 204/revocation.
Сырой content соответствует сохранённым пяти полям; trace и review совпадают.
Браузер: вход → карточка → trace → 20 findings; console warn/error=[].

Замечание тестовой среды: Windows checkout изменил только LF на CRLF у frozen
reviewer-файлов. Точное совпадение существующих hashes восстановлено нормализацией
переносов строк; никакие правила, holdout и freeze не менялись.
Для воспроизводимости checkout добавлен .gitattributes только для этих семи файлов;
сохранён исходный mixed EOL freeze (один файл CRLF, остальные LF).

## Финальная проверка восстановления v1.25.1

Существующая реализация сохранена; повторный полный прогон не выполнялся.
Проверены сохранённые результаты тестов, все frozen SHA-256 и сохранность 46 исходных документов/артефактов. Git diff --check пройден.
Шесть путей отображаются Git как изменения переносов строк, но нормализованное содержимое совпадает с HEAD; правила и контрольные hashes не изменены.

При первом диагностическом падении pytest в вывод попал DSN исключительно собственной тестовой БД. Пароль этой БД заменён; текущие параметры находятся только в ignored private-файлах. Ключ LLM не использовался.

### Полный перечень содержательных изменений (23 файла)

- backend/.dockerignore
- backend/Dockerfile
- backend/api/auth.py
- backend/api/news.py
- backend/tests/conftest.py
- frontend/src/pages/Insight.tsx
- frontend/src/shared/api/mappers/pulseMappers.ts
- frontend/src/store/models/IPulse.ts
- frontend/src/widgets/Company/AboutCompany.tsx
- frontend/src/widgets/Insight/InsightSections.tsx
- frontend/src/widgets/Insight/InsightSidePanel.tsx
- frontend/src/widgets/Layout/AlfaLayout.tsx
- .gitattributes
- backend/fixtures/saved_llm_pilot_v1.json
- backend/saved_pilot_demo.py
- backend/tests/test_auth_saved_pilot_demo.py
- backend/tests/test_saved_pilot_demo.py
- compose.saved-pilot-demo.yml
- database/saved-pilot-demo-marker.sql
- docs/SAVED_LLM_PILOT_DEMO.md
- frontend/src/shared/constants/savedPilot.ts
- frontend/src/widgets/Insight/SavedPilotNotice.test.tsx
- frontend/src/widgets/Insight/SavedPilotNotice.tsx

### Только восстановление исходных переносов строк (6 файлов)

- backend/services/financial_scope.py
- backend/services/financial_review_service.py
- backend/services/local_adaptive_service.py
- backend/evaluation/quality.py
- backend/evaluation/quality_scope.py
- backend/evaluation/quality_holdout_v2.json
