# Расширенная saved-pilot коллекция — v1.29.0

- 3 синтетические компании, по3 сохранённых настоящих инсайта:9 всего.
- Чистый Docker build/Compose без .env: PASS; PostgreSQL/backend/frontend healthy, seed exit0.
- Обновление отдельного тома v1.28.2: PASS, исходный анализ/evidence/trace и посторонняя запись сохранены.
- Повторный seed: created0 / unchanged8, без новых LLM-вызовов и дубликатов.
- nginx HTTP: 50 проверок PASS на чистой и upgrade-копии.
- Browser: 3 компании ×3 инсайта, ссылки, trace, reviewer; console errors/warnings0.
- Backend109 профильных тестов PASS; frontend14 PASS, TypeScript/build PASS.
- Достоверность финансовых выводов не подтверждена; источники исторические, не банковские PDF.
- Подробнее: [SAVED_PILOT_COLLECTION.md](SAVED_PILOT_COLLECTION.md).

Ниже сохранены исторические результаты предыдущих релизов, а не текущий объём коллекции.

# Публичный saved-pilot — v1.28.0

Проверен отдельный запуск из clean-context: отслеживаемые файлы HEAD плюс только
перечисленные изменения этой задачи; ignored backend/data, .env и приватные
артефакты не копировались. Исключение — собственный .env, созданный по инструкции.
Сборка использовала cache зависимостей, не prebuilt приложение.

- Backend Dockerfile.saved-pilot и frontend Dockerfile: BUILD PASS.
- TypeScript + Vite production build: PASS.
- Compose: отдельный project pulse-public-pilot-check-20261026, новый том/БД,
  postgres/backend/frontend healthy, seed Exited(0).
- nginx: 17 HTTP-проверок, login/me/profile/feed/card, 401/403/logout204.
- Read-only: запрещены POST news и оба маршрута анализа; чужая компания403.
- Ответ модели, 2 evidence, все 20 findings и trace совпадают с pinned fixture.
- Повтор seed: UNCHANGED, без новых записей и SDK-запросов.
- PostgreSQL: rollback при втором evidence и trace, 8 concurrent imports
  (1 CREATED, 7 UNCHANGED), отказ для неверного marker/пароля/непустой БД.
- Browser: вход → единственная компания → лента → карточка; видны синтетическое
  происхождение, сохранённый настоящий ответ, учебные TXT и financial warnings.
  Console errors/warnings отсутствуют.
- Reviewer: 16 UNKNOWN, 4 NEEDS_REVIEW. Достоверность не подтверждена.
- Новых LLM-запросов: 0. Действующие 8080/8081 не изменялись.

Для этой машины .env задаёт проверенную свободную подсеть 172.16.253.0/24.
Шаблонную подсеть нельзя копировать без проверки пересечений. Приватный .env,
контекст сборки, HTTP-результаты остаются в ignored backend/data/public_pilot_check.
Ни CSV, ни банковские PDF для этого запуска не нужны.

Ниже сохранён прежний отчёт fake submission v1.27.2. Это отдельная проверка,
не оценка финансовой достоверности saved-pilot.

# Проверка сдаваемого окружения — 26 октября 2026

Проверенная версия: v1.27.1, коммит
f3367ddd81255857eab929715f787b7890dce6e8. Docker-проверка выполнена на этом
коммите; v1.27.2 обновляет только документацию, без изменения проверенного кода.
Инструкция запуска — для main.

## Итоговый статус

| Проверка | Результат |
|---|---|
| Docker BUILD | PASS — оба submission image собраны из исходников |
| Docker Compose | PASS |
| nginx E2E | PASS — 22 HTTP-проверки через localhost:8080 |
| Browser smoke | PASS — console errors/warnings отсутствуют |
| PostgreSQL / backend / frontend | healthy |
| Seed | Exited (0) |

Подтверждён только **синтетический demo-режим с fake transport**.
Настоящих LLM-вызовов в этой проверке — 0. Organizer override не использовался;
проверка реального LLM-режима в рамках этого E2E не заявляется.
Корректный JSON, provenance и reviewer не доказывают финансовую достоверность.

Backend build: **98,42 секунды**, frontend build: **67,50 секунды**.
Сборки шли параллельно, общий порядок времени — около 1 минуты 40 секунд.
Использован сохранённый кэш загрузок, без общего лимита в 240 секунд.
Это сборка опубликованных Dockerfiles, а не временный образ на старом runtime.
Внутри frontend build прошли TypeScript и production Vite build.

Ранее загрузки PyPI/registry были медленными и сборки останавливались.
Последующая успешная сборка и nginx/browser smoke закрыли прежний технический
блокер. На машине жюри доступ к registries при первой сборке всё ещё необходим;
резервный перенос готовых образов описан в README.

## Проверенное окружение

- Отдельный project pulse-submission-clean-20261026 и собственный именованный том.
- БД test_submission_demo, marker pulse:isolated-company-import:v1.
- Schema и миграции 002–007 применены; 22 public таблицы.
- Два синтетических профиля, demo-analyst и memberships созданы seed.
- Backend: AI_MODE=demo, DATASET_AI_TRANSPORT=fake, пустой LLM_API_KEY.
- Проверен SHA-256 release manifest внутри runtime.
- В backend image нет /app/data: локальные private artifacts не требуются.
- Сервисы используют поставляемые synthetic fixtures; CSV организаторов,
  реальные платежи, банковские PDF и настоящий API-ключ не нужны.
- Приложение: http://localhost:8080; backend: http://localhost:8000.
- pip check: No broken requirements found; nginx -t: successful.

Локальный .env содержит только настройки по README и исключён из Git.
Пароли и токены в отчёт не включены. Конфигурация, зависимости и бизнес-логика
для успешного запуска не менялись.

## nginx E2E: 22 HTTP-проверки

Все запросы отправлены через nginx, а не напрямую на backend:

- /, React deep link /pulse/insights, /health, /ready, /docs и /openapi.json — 200.
- В OpenAPI проверены конкретные login/me/profile/capabilities/dataset routes.
- Без сессии и с неверным паролем — 401.
- Login demo-analyst, /api/me с двумя компаниями и оба профиля — 200.
- Чужая компания — 403; capabilities и лента доступны своей компании.
- Новая синтетическая новость — 201; fake-анализ — 201 COMPLETED.
- Карточка содержит результат, один TXT evidence, financial_review и orchestration.
- Повтор той же пары — 200, тот же insight, без нового анализа.
- Сохранённый результат присутствует в ленте.
- Logout — 204; отозванная сессия при следующем /api/me — 401.

## Browser smoke

В браузере через http://localhost:8080 проверены:

1. Login с серверной учётной записью demo-analyst.
2. Список двух доступных компаний, выбор первой и профиль из PostgreSQL.
3. Ввод новой синтетической новости, подтверждение права на текст и fake-анализ.
4. «Инсайт готов», переход в карточку и отображение исходного текста и результата.
5. TXT-источник, отсутствие приписанной позиции Альфа-Банка и financial review.
6. Предупреждения «Локальная заглушка — LLM не вызывалась» и
   «Финансовая достоверность не подтверждена».
7. Logout с возвратом на страницу входа.

Console errors/warnings в проверенной вкладке отсутствуют.
Browser-проверка cache отдельно не выполнялась: cache подтверждён HTTP-сценарием.

## Network override — резерв для исчерпанных address pools

На этой машине стандартные Docker address pools исчерпаны другими сохранёнными
сетями. Успешный запуск выполнен с документированным override:

~~~powershell
docker compose -p pulse-submission-clean-20261026 -f compose.submission.yml -f compose.submission.network.yml up --no-build --pull never -d --wait
~~~

SUBMISSION_SUBNET задан в локальном .env. Подсеть 172.16.251.0/24 проверена
на отсутствие пересечений перед созданием собственной сети. У другого пользователя
она может быть занята — нельзя копировать её автоматически.
Базовый запуск без network override на этой машине не проверялся из-за адресных
пулов; это не ошибка приложения. Default Compose не задаёт собственную подсеть.
При использовании override добавлять его ко всем командам окружения.
Чужие сети, контейнеры, образы и тома не удалялись и не менялись.

## Ранее выполненные проверки подготовки

Эти результаты сохраняются как ранее полученные, а не как повторный прогон:

- 31 targeted pytest: packaging (5), Docker-контракты и dataset policy (26).
- Строгий audit двух синтетических профилей, file/row hashes release, fake DTO.
- pip check и npm ls без нарушений зависимостей.
- 20 direct-backend HTTP проверок на отдельном runtime smoke-образе.
  Они не засчитываются в новые 22 проверки через nginx.
- Повтор seed и restart: профили, memberships, результаты и evidence сохранены,
  контрольные отпечатки прежних результатов неизменны.
- 7 frozen raw SHA-256 и 46 защищённых прежних документов/артефактов сохранены.
- git diff --check без ошибок; шесть прежних EOL-only файлов не включались в коммит.

Полная регрессия и платные LLM-вызовы при Docker smoke не запускались.

## Зависимости и ограничения

35 закреплённых web Python пакетов, 540 npm inventory entries из lock,
304 upstream LICENSE/NOTICE блока в THIRD_PARTY_NOTICES.md.
OCR stack не входит в submission runtime; PyMuPDF отдельно отмечен как
AGPL/commercial. Проектная лицензия автоматически не назначалась.
Полный CVE/security и юридический аудит зависимостей не выполнялся.

- Тариф/квота организаторов и централизованный денежный бюджет в этом E2E
  не проверялись; для fake demo они не нужны.
- Реальный organizer требует отдельного подтверждения, точного preflight и ключа.
- COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED, ACL, jobs и retry policy сохранены.
- Полностью без-Docker запуск не проверен и как готовый вариант не заявляется.
- Архив docker save/load не создавался и отдельно не проверялся.
- Финансовая достоверность и production-готовность этим smoke не подтверждаются.

## Подготовленные файлы v1.27.1 (20)

- README.md
- .env.example
- THIRD_PARTY_NOTICES.md
- compose.submission.yml
- compose.submission.organizer.yml
- compose.submission.network.yml
- docker/submission-marker.sql
- backend/.dockerignore
- backend/Dockerfile.submission
- backend/requirements-runtime.txt
- backend/submission_demo.py
- backend/fixtures/submission_profiles.json
- backend/fixtures/submission_release.json
- backend/fixtures/submission_rag/synthetic-rate.json
- backend/tests/test_submission_packaging.py
- frontend/.dockerignore
- frontend/Dockerfile
- frontend/nginx.conf
- docs/JURY_DEMO.md
- docs/SUBMISSION_CHECK.md

Итоговый локальный отчёт, HTTP checks и build logs сохранены только в ignored
backend/data/submission_check. Секреты и локальные артефакты не поставляются.
Текущее обновление документации затрагивает только README.md и данный отчёт;
новой сборки, LLM-вызовов или повторной регрессии для него не выполнялось.
