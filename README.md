# Пульс бизнеса — версия для сдачи v1.31.2

## Рекомендуемый запуск для жюри — одна команда, без .env

Нужны Git, Docker Desktop с Linux containers, Docker Compose v2 и доступ к
registries при первой сборке. Из корня свежего клона, **без создания .env**:

~~~powershell
docker compose -f compose.saved-pilot-demo.yml up --build -d --wait
~~~

- Приложение: **http://localhost:8082**; Swagger: http://localhost:8010/docs.
- Используется **один общий демонстрационный аккаунт**:
  логин **synthetic-pilot-viewer**, пароль **PulseDemo2026Viewer**.
- После входа переключайтесь между тремя синтетическими компаниями прямо в интерфейсе:
  нажмите **название текущей компании в правой части верхней панели, над логином**
  (рядом стрелка вниз), затем выберите компанию в меню **«КОМПАНИИ ПО ВАШЕМУ ЛОГИНУ»**.
- Откройте Пульс → Инсайты: у каждой компании **3 сохранённых LLM-инсайта**, всего **9**.
- Для просмотра другой компании **не нужно выходить из аккаунта или вводить другие credentials** —
  достаточно выбрать её в том же меню.

Это девять сохранённых **настоящих ответов DeepSeek на синтетических компаниях и
новостях**, не новый live-анализ и не fake-ответ. Три компании: металлургия, розница
и производство оборудования; по три инсайта на каждую. Исторический первый ответ
сохранён без изменений. Его два источника — учебные TXT; восемь новых ответов
используют короткие исторические публичные фрагменты ЦБ, ЕК, Всемирного банка и
других первоисточников с датами и ссылками. Это **не аналитика Альфа-Банка**.
Новых LLM-вызовов нет; API-ключ не нужен и в контейнере принудительно пуст.
Финансовая достоверность не подтверждена. Исторический ответ сохраняет
**16 UNKNOWN и 4 NEEDS_REVIEW**; у новых ответов собственные findings и оговорки
экспертного просмотра. JSON/provenance и наличие ссылки не доказывают вывод.
Даты генерации и импорта показаны отдельно; дата публикации одного источника МСП
неизвестна (известна только дата события). Обрезанная попытка в demo не включена.

Обновление тома v1.28.2: та же команда добавит восемь результатов одной транзакцией,
сохранив исторический инсайт и посторонние записи. Повторный запуск не создаёт
дубликаты. При несовпадении хешей/идентификаторов seed завершится с ошибкой без
частичного импорта. Не очищайте том для обхода ошибки — сохраните логи и проверьте
причину. Схема БД и контракт API не меняются.

**Credentials публичные и предназначены исключительно для локального synthetic demo.**
Пароль PostgreSQL `0123456789abcdef0123456789abcdef` также публичный, отдельный
от пароля входа. Они непригодны для production. Не публикуйте это окружение в
Интернет, не подключайте к нему реальные данные. Порты привязаны к `127.0.0.1`,
PostgreSQL наружу не публикуется, аккаунт read-only. Это не режим банковского входа.

### Проверка запуска, перезапуск и старые тома

~~~powershell
docker compose -f compose.saved-pilot-demo.yml ps -a
docker compose -f compose.saved-pilot-demo.yml logs --tail=40 seed backend
curl.exe http://localhost:8010/ready
~~~

Успех: postgres/backend healthy, seed Exited(0), frontend Up; `/ready` — HTTP 200,
`database=true`. В offline-режиме `rag=false` и `llm_config=false` нормальны:
`diagnostics.required_checks` содержит только `database`.
Seed проверяет закреплённые хеши, изоляцию БД, TCP credentials и неизменность импорта.
Повторный запуск не создаёт дубликаты и не меняет исходный ответ/reviewer/trace.

~~~powershell
docker compose -f compose.saved-pilot-demo.yml stop
docker compose -f compose.saved-pilot-demo.yml up --no-build --pull never -d --wait
~~~

**v1.28.2 использует новый project `pulse-saved-pilot-public` и том с ключом
`saved_pilot_public_v1282_data`.** Прежний `pulse-saved-pilot-demo` и его
`saved_pilot_pgdata` не используются, не удаляются, пароли старой БД не меняются.
Новый demo создаёт собственную копию того же закреплённого синтетического пилота.
Не подставляйте старый том вручную: неподходящие credentials/состояние приводят
к отказу, а не автоматической смене пароля или очистке БД.

### Необязательная настройка портов и сети

Существующий `.env` не требуется. Значения `SAVED_PILOT_DB_PASSWORD` и
`SAVED_PILOT_DEMO_PASSWORD` из старого `.env` **игнорируются**: demo использует
фиксированные публичные значения из Compose. При этом стандартные настройки
Compose (`COMPOSE_PROJECT_NAME`, `COMPOSE_FILE` и т.п.) и опциональные переменные
портов по-прежнему действуют. Не используйте имя проекта старого окружения.

Если порты заняты (`port is already allocated` / `address already in use`), задайте
свободные `SAVED_PILOT_FRONTEND_PORT` и `SAVED_PILOT_PORT` в локальном окружении.
Например, только после проверки свободных портов в PowerShell:

~~~powershell
$env:SAVED_PILOT_FRONTEND_PORT = '8086'
$env:SAVED_PILOT_PORT = '8016'
docker compose -f compose.saved-pilot-demo.yml up --build -d --wait
~~~

Теперь приложение на http://localhost:8086, Swagger/readiness на порту 8016.
Если старый `.env` содержит эти переменные, его значения также меняют порты;
проверьте их или задайте явные значения в окружении. API через nginx остаётся same-origin.

По умолчанию Docker сам выделяет сеть. `SAVED_PILOT_SUBNET` из старого `.env`
не влияет на основной Compose. При `address pools exhausted` или конфликте сети
проверьте `docker network ls`, `docker network inspect <имя>` и маршруты хоста
(`route print` в Windows). Выберите собственную свободную подсеть и **только тогда**:

~~~powershell
$env:SAVED_PILOT_SUBNET = '<проверенная-свободная-подсеть-CIDR>'
docker compose -f compose.saved-pilot-demo.yml -f compose.saved-pilot.network.yml up --build -d --wait
~~~

Этот override добавляйте ко всем дальнейшим командам данного окружения.
Не удаляйте чужие сети/тома и не применяйте prune или `down -v`.
Смена подсети уже созданной сети не является обычным restart; используйте новый
отдельный project с собственными свободными портами/подсетью либо согласованную
процедуру остановки только своего окружения с сохранением тома.

При `SAVED_PILOT_BACKEND_DATABASE_CHECK_FAILED` /
`DATABASE_AUTHENTICATION_FAILED` seed останавливается до импорта. `/ready`
работающего backend показывает безопасный `diagnostics.database_code`.
В новом фиксированном режиме изменение старых password-переменных `.env` это
не исправляет. Проверьте, что запущен именно новый project и не подключён чужой том.
Для восстановления **старого** окружения v1.28.1 нужны прежняя конфигурация и
первоначальные пароли; не меняйте пароль существующей БД автоматически.
При `DATABASE_TABLE_MISSING` / `DATABASE_*_SCHEMA_MISMATCH` проверьте миграции и
целевую БД, не обходите readiness. [Происхождение ответа](docs/SAVED_LLM_PILOT_DEMO.md).

## Проверка live-анализа жюри

### Информация для жюри

- **Команда: The Yabliki**
- **Проект: Пульс бизнеса**
- **Трек: Новостная аналитика**

Для проверки live-анализа необходим API-ключ организаторов хакатона. При запросе,
получении или активации ключа укажите название команды **«The Yabliki»**, чтобы
организаторы могли идентифицировать проект. Используйте предоставленный организаторами
ключ или собственный совместимый ключ, если он принимается указанным шлюзом и
поддерживает указанный API и модель. Другие провайдеры автоматически не выбираются.

Ключ записывается **только в локальный `.env`, в переменную `LLM_API_KEY`**.
Настоящие ключи запрещено публиковать в GitHub, README, коммитах и логах.
Сохранённые анализы трёх синтетических компаний доступны **без API-ключа**.

**[Шесть готовых тестовых новостей и сценарий персонализации](docs/JURY_TEST_NEWS.md).**
Все события и цифры вымышлены; это входные данные, не готовые ответы модели.
Для быстрой проверки достаточно одной новости; сравнение трёх компаний занимает
несколько запросов и расходует `LIVE_SYNTHETIC_MAX_REQUESTS`.

### Запуск live-режима

Нужны Git, Docker Desktop с Linux containers, Docker Compose v2, интернет для первой
сборки и **собственный действующий API-ключ шлюза организаторов**. Офлайн-запуск выше
по-прежнему не требует ключа или `.env`. Для отдельного live-режима (PowerShell):

```powershell
git clone https://github.com/KefirMira/TheYabliki-alpha-hackathon.git
cd TheYabliki-alpha-hackathon
Copy-Item .env.example .env
```

В редакторе заполните **`LLM_API_KEY` в локальном `.env`**. Остальные live-настройки
уже заданы: `LLM_BASE_URL=https://changellenge.up.railway.app/v1`,
`LLM_MODEL=deepseek/deepseek-v4.1-flash`, `LIVE_SYNTHETIC_ANALYSIS_ENABLED=true`,
`AI_MODE=full`, `SAVED_PILOT_OFFLINE=0`, `LIVE_SYNTHETIC_MAX_REQUESTS=5`.
Поля `SUBMISSION_*` не используются этим Compose. Не коммитьте `.env` и не вводите
ключ во frontend. После заполнения ключа запуск одной командой:

```powershell
docker compose -f compose.live-synthetic.yml up --build -d --wait
```

- Приложение: **http://localhost:8092**; API: http://localhost:8012/docs.
- Логин **synthetic-pilot-viewer**, пароль **PulseDemo2026Viewer**.
- Нажмите название компании над логином в верхней панели, выберите одну из трёх
  синтетических компаний; повторный вход не нужен.
- Пульс → Инсайты → **«Проанализировать новость»**. Введите заголовок и текст,
  необязательный URL; подтвердите право передачи текста и нажмите **«Проанализировать»**.
  Не вводите конфиденциальные данные. Открытие страницы само не вызывает LLM.
- Ожидаются вывод, риски, возможности, рекомендации, usage, SHA-256 и reviewer.
  Внешние источники не предоставлены — это явно указано, ссылки не выдумываются.

Окружение имеет собственные project `pulse-live-synthetic-demo`, PostgreSQL
`test_live_synthetic_demo` и том `live_synthetic_demo_data`. Оно не использует offline-том.
Прежний seed автоматически создаёт три синтетические компании, девять сохранённых
анализов и read-only пользователя с серверными ACL. Публичные credentials предназначены
только для **localhost**; не выставляйте это окружение в Интернет или production.
Ключ передаётся только backend при запуске — не frontend, seed или в build args.

Проверка запуска и безопасная остановка:

```powershell
docker compose -f compose.live-synthetic.yml ps -a
docker compose -f compose.live-synthetic.yml logs --tail=30 seed backend
docker compose -f compose.live-synthetic.yml stop
```

Успех: seed Exited(0), PostgreSQL/backend/frontend healthy. Live-healthcheck проверяет
изолированную БД, read-only memberships и opt-in конфигурацию без LLM-вызова.
Общий `/ready` не изменён: при `rag=false` и `database=true` он может вернуть503;
это не ошибка БД. При неверном ключе/квоте сам анализ завершится ошибкой без повторов.
Если порты заняты, измените `LIVE_SYNTHETIC_FRONTEND_PORT` и `LIVE_SYNTHETIC_BACKEND_PORT`
в `.env`. При конфликте подсети проверьте Docker-сети и маршруты хоста, затем задайте
свободную `LIVE_SYNTHETIC_SUBNET`. Не удаляйте чужие сети/тома и не используйте `down -v`.

Ограничения: только три разрешённых **синтетических профиля из fixtures** — DB-контекст
не отправляется. Новость непроверенная; URL не скачивается. **RAG и банковские PDF не
подключены. Результат не сохраняется в БД/ленту** и исчезнет после обновления страницы.
Девять сохранённых анализов не меняются. Финансовая достоверность не подтверждена;
UNKNOWN/NEEDS_REVIEW требуют экспертной оценки.

Один запрос на отправку, без retries/fallback; вход до8000 токенов с консервативной
оценкой по UTF-8-байтам, выход до4000 включая reasoning; SDK timeout60с, операция120с.
Лимит5 по шаблону (допустимо1–20) действует **в пределах процесса**, сбрасывается при
рестарте и не общий между workers. Это **не гарантия денежного лимита команды**.
Не повторяйте запрос с неизвестным исходом автоматически. Seed и healthcheck не вызывают LLM.

Вернуться к offline-demo можно после остановки live, сохранив все данные:

```powershell
docker compose -f compose.saved-pilot-demo.yml up --build -d --wait
```

Offline-приложение: http://localhost:8082. Ключ и live-переменные из `.env` не включают
LLM в offline-Compose; он продолжает работать без API-ключа.

## О продукте и ранее проверенном техническом demo

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
