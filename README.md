# Пульс бизнеса — версия для сдачи v1.28.0

«Пульс бизнеса» помогает оценивать влияние новости на выбранную компанию:
сопоставляет её с контекстом компании и аналитическими материалами, показывает
риски, возможности и рекомендации со ссылками на источники. Интерфейс разделяет
факты новости, подтверждённую позицию источника и выводы AI.

React + FastAPI + PostgreSQL. Для жюри рекомендуем **сохранённый настоящий ответ
DeepSeek на полностью синтетических данных** (offline, read-only). Отдельный
технический fake-режим сохранён. Новый LLM-вызов не нужен для запуска; ключи,
реальные CSV и банковские PDF не поставляются.

**Технический fake submission проверен 26 октября 2026:** Docker BUILD и Compose — PASS;
nginx E2E — PASS (22 HTTP-проверки); browser smoke — PASS, без console errors
и warnings. PostgreSQL, backend и frontend — healthy, seed завершился с кодом 0.
Подтверждён **синтетический demo с fake transport**, без платных запросов.
Organizer/реальный LLM в этом E2E не проверялся. Сборка выполнена из исходников
с сохранённым кэшем загрузок; на проверенной машине применён документированный
network override. Подробности — в [SUBMISSION_CHECK](docs/SUBMISSION_CHECK.md).

## Рекомендуемый запуск для жюри: сохранённый настоящий LLM-пилот

Это содержательный **исторический ответ DeepSeek на полностью синтетических данных**,
а не новый live-анализ и не fake-ответ. Одна компания, одна новость, один исходный
ответ и два учебных TXT-источника. Банковских PDF и датасета организаторов здесь нет.
Финансовая достоверность не подтверждена: **16 UNKNOWN и 4 NEEDS_REVIEW**.

Нужны Git, Docker Desktop (Linux containers), Compose v2, доступ к registries при
первой сборке. Из checkout `main`:

~~~powershell
Copy-Item .env.example .env
~~~

В `.env` задайте `SAVED_PILOT_DB_PASSWORD` (32–128 hexadecimal символов,
например `[guid]::NewGuid().ToString('N')`) и `SAVED_PILOT_DEMO_PASSWORD`
(свой пароль 12–256 символов). Не оставляйте `REPLACE_*`. API-ключ не нужен.
Проверьте, что `SAVED_PILOT_SUBNET` не пересекается с сетями Docker/маршрутами
хоста; при необходимости укажите свою свободную подсеть. Не удаляйте чужие сети.

**Одна команда сборки, миграций, импорта и запуска:**

~~~powershell
docker compose -f compose.saved-pilot-demo.yml up --build -d --wait
~~~

- Приложение: **http://localhost:8082**, Swagger: http://localhost:8010/docs.
- Логин: **synthetic-pilot-viewer**. Пароль — ваш `SAVED_PILOT_DEMO_PASSWORD`.
- Войти → выбрать единственную синтетическую компанию → Пульс → Инсайты → карточка.
- Видны исходный ответ, риски, возможности, рекомендации, два учебных источника,
  исторический trace и все предупреждения reviewer. Это не подтверждённая
  финансовая рекомендация. Аккаунт read-only: новые анализы запрещены.
- Новый LLM-запрос не выполняется; ключи провайдера в этом режиме принудительно пусты.

Отдельные project `pulse-saved-pilot-demo`, БД и том не затрагивают fake submission.
Seed проверяет закреплённые хеши, пустоту новой БД либо неизменность прежнего импорта.
Повторный запуск не удваивает записи. Не меняйте пароли после создания тома:
несовпадение приводит к отказу, а не сбросу данных.

~~~powershell
docker compose -f compose.saved-pilot-demo.yml logs --tail=80 seed backend frontend
docker compose -f compose.saved-pilot-demo.yml stop
~~~

Тома сохраняются. Для повторного старта — та же команда без `--build`.
При занятых портах измените `SAVED_PILOT_FRONTEND_PORT` / `SAVED_PILOT_PORT`.
[Подробности и происхождение ответа](docs/SAVED_LLM_PILOT_DEMO.md).

## Отдельный технический режим: fake submission

Следующая инструкция запускает **другое окружение на 8080**, где новые запросы
обрабатываются локальной заглушкой. Для первого знакомства жюри используйте saved-pilot выше.

## Чистый запуск — без установки Python и Node.js

Нужны Git, Docker Desktop с Linux containers и Docker Compose v2
(поддержка service_completed_successfully / up --wait), доступ к Docker Hub,
PyPI и npm при первой сборке. Предусмотрите около 4–6 GB свободного места
и не менее 4 GB памяти Docker. Сборка загружает зависимости.

Из корня checkout ветки main:

~~~powershell
Copy-Item .env.example .env
~~~

В локальном .env замените только два обязательных значения:
- SUBMISSION_DB_PASSWORD — собственная строка из 32–128 hexadecimal символов;
- SUBMISSION_DEMO_PASSWORD — собственный пароль длиной от 12 символов.

Пример генерации DB-пароля в PowerShell: [guid]::NewGuid().ToString('N').
Пароли и содержимое .env не публикуйте; .env исключён из Git.
Остальные значения шаблона можно оставить. Шаблонные REPLACE_* seed не принимает.

~~~powershell
docker compose -f compose.submission.yml up --build -d --wait
~~~

Compose создаст отдельный project pulse-submission, сеть и именованный том.
Применятся schema + миграции 002–007, затем синтетический seed.
Seed автоматически создаёт две компании, учётную запись и memberships.
Пользовательские новости и grants создаются обычным POST /api/news после входа.
Insight появляется после нажатия анализа; заранее готового fake COMPLETED не подставляется.
Реальные импорты вручную выполнять не нужно.

## Адреса и аккаунт

- Приложение: http://localhost:8080
- Backend: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Проверки: /health и /ready
- Login: **demo-analyst**, пароль — SUBMISSION_DEMO_PASSWORD из вашего .env.
- Компании: SYNTH-SUBMISSION-001 (учебное производство оборудования) и
  SYNTH-SUBMISSION-002 (учебная разработка ПО).

Frontend обслуживается nginx, API идёт через same-origin proxy; deep links
React работают после перезагрузки страницы. PostgreSQL наружу не публикуется.
Оба опубликованных HTTP-порта привязаны только к 127.0.0.1.
При конфликте портов задайте SUBMISSION_FRONTEND_PORT / SUBMISSION_BACKEND_PORT
в .env. Предпочитайте localhost; desktop и внешняя публикация требуют отдельной настройки.

## Проверка и демонстрация

1. Войти, выбрать компанию, открыть профиль.
2. Открыть Пульс -> Инсайты -> Проанализировать новость.
3. Вставить синтетический текст из [сценария жюри](docs/JURY_DEMO.md).
4. Подтвердить право передачи текста. В default fake-режиме внешней передачи нет.
5. Запустить, открыть результат, увидеть источники и UNKNOWN/NEEDS_REVIEW.
6. Вернуться в ленту. Повтор той же пары возвращает cache без нового draft.
7. Выйти: сервер отзовёт сессию.

Строгая серверная авторизация, ACL компании/news и прежние jobs включены.
Никакого общего токена или обхода пароля нет.
Финансовая достоверность не подтверждается JSON/provenance или пустыми warnings.

## Логи, повторный запуск и остановка

~~~powershell
docker compose -f compose.submission.yml ps -a
docker compose -f compose.submission.yml logs --tail=100 seed backend frontend
docker compose -f compose.submission.yml run --rm seed
docker compose -f compose.submission.yml stop
docker compose -f compose.submission.yml up -d --wait
~~~

Seed идемпотентен: повтор не очищает новости/insights и не меняет старые результаты.
Не меняйте DB/demo пароль в .env после создания тома: это не инструмент
ротации credentials. При несовпадении seed останавливается, а не исправляет БД.
Для нового независимого набора используйте новый Compose project и свободные
порты с отдельными сохранёнными env-настройками.
Не используйте prune / down -v и не удаляйте чужие Docker-ресурсы.

## Fake и organizer — явное разделение

compose.submission.yml жёстко задаёт DATASET_AI_TRANSPORT=fake и пустые LLM env.
Даже наличие LLM_API_KEY в .env не включает платную модель.

[compose.submission.organizer.yml](compose.submission.organizer.yml) — отдельный
**необязательный и платный opt-in**, только после отдельного разрешения:
- ключ хранится в локальном окружении/.env, не в Git;
- модель deepseek/deepseek-v4.1-flash, только основной шлюз организаторов;
- нужны DATASET_AI_REAL_CONFIRMED=one-bounded-draft-approved и hash
  конкретной новой пары в DATASET_AI_REAL_PAIR_SHA256;
- сначала read-only preflight точного DTO по [инструкции v1.27](docs/HACKATHON_DATASET_ANALYSIS.md);
- один draft, <=8000 input allowance, <=2000 output включая reasoning,
  SDK 60 s / сервис 120 s, без retries и fallback;
- разрешена только первая попытка; FAILED/unknown не повторять автоматически.

Только после нового согласования:
~~~powershell
docker compose -f compose.submission.yml -f compose.submission.organizer.yml up -d --wait backend
~~~

Эта команда лишь включает явно подтверждённую конфигурацию; модель вызывается
только соответствующим POST анализа. Для возврата к fake:
~~~powershell
docker compose -f compose.submission.yml up -d --wait backend
~~~

COMPLETED cache не заменяется реальным анализом. Для live smoke нужна новая
новость, а не удаление истории. Глобальный COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED
для остальных DB-контекстов не отключается.
Локальные лимиты не гарантируют денежный лимит команды.

## Что поставляется и что не входит

В техническом fake submission нет реальных платежей, F–U связей, закрытых
материалов и сырых ответов платных пилотов. Отдельный saved-pilot содержит только
проверяемый синтетический экспорт одного исторического ответа, описанный выше. Существующий успешный live smoke доказывает технический
путь, а не качество или финансовую достоверность всех выводов.
Сохранённый live-результат можно показать отдельно в проверенном локальном
окружении без нового запроса; он не подменяет clean fake demo.

Нет полноценной банковской авторизации, реальных платежей, SMS/email recovery,
автоматического RSS или массового AI. Часть банковской витрины — явно обозначенное
демо. Избранное/скрытие инсайтов остаются локальными настройками браузера.
Production deployment/TLS/централизованный денежный бюджет не входят в сдачу.

## Зависимости и лицензии

- Backend submission: backend/requirements-runtime.txt, закреплённые web-зависимости.
- Frontend: npm ci по frontend/package-lock.json.
- [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md) содержит inventory и upstream notices.
- OCR/PDF toolchain из backend/requirements.txt не установлен в submission image;
  PyMuPDF имеет AGPL/commercial-условия, отдельно от web-runtime.
- Лицензии dataset/закрытых PDF и разрешение gateway не предоставляются этим репозиторием.
- Проектная лицензия на собственный код автоматически не назначалась.

Технические детали: [dataset API/policy](docs/HACKATHON_DATASET_ANALYSIS.md),
[подготовка сдачи и smoke](docs/SUBMISSION_CHECK.md).

### Если Docker исчерпал address pools

Не удаляйте чужие сети. Проверьте `docker network inspect` и маршруты хоста,
выберите свободную приватную подсеть и задайте `SUBMISSION_SUBNET` в локальном .env.
Затем используйте дополнительный override во всех командах этого окружения:

~~~powershell
docker compose -f compose.submission.yml -f compose.submission.network.yml up --build -d --wait
~~~

Override создаёт собственную сеть, не подключает приложение к чужой сети.
Не копируйте подсеть другого окружения без проверки отсутствия пересечений.

### Резервный вариант при недоступных PyPI/registry на машине жюри

На машине сборки с рабочим доступом к registries сначала успешно выполните
обычную сборку и smoke из этой инструкции. Затем можно передать **готовые образы**
отдельным архивом (не добавлять его в Git):

~~~powershell
docker compose -f compose.submission.yml build backend frontend
docker compose -f compose.submission.yml pull postgres
docker save -o ../pulse-submission-images.tar pulse-submission-backend:local pulse-submission-frontend:local postgres:16
Get-FileHash ../pulse-submission-images.tar -Algorithm SHA256
~~~

На машине жюри: проверить согласованный SHA-256 архива, загрузить образы,
создать собственный .env по инструкции выше и запустить без сборки:

~~~powershell
docker load -i ../pulse-submission-images.tar
docker compose -f compose.submission.yml up --no-build --pull never -d --wait
~~~

Архив должен быть собран именно из проверенных submission Dockerfiles,
а не из временного smoke-образа на старом runtime. Пароли и API-ключи в образы
не встраиваются; пользовательские значения задаются только локальным .env.
Если нужны настройки собственной подсети, добавить network override и сюда.

### Запуск полностью без Docker

Полный сквозной запуск этой submission-конфигурации без Docker не проверен.
Успешные локальные TypeScript/production build и прежняя интеграция не подтверждают
чистую установку PostgreSQL, seed и всего приложения на машине жюри без Docker.
Поэтому непроверенная альтернативная инструкция здесь не предлагается.
Вариант с docker load выше требует Docker и предварительно проверенного архива.
