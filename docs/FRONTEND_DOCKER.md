# Backend для frontend: Docker, версия v1.9.0

Нужны Git и Docker Desktop (Linux containers) либо Docker Engine с Compose v2.
Python на компьютере не нужен. Выполнять команды из корня checkout ветки
`feature/ai-db-integration`, содержащей этот файл. Пока v1.9.0 не опубликована,
команды доступны только в локальном checkout автора.

## Demo: одна команда запуска

```sh
docker compose -p pulse-frontend-demo -f compose.frontend.yml up -d --build --wait --wait-timeout 180
```

Первый запуск скачивает образы и Python-зависимости. На новой пустой БД PostgreSQL
автоматически применяет исходную schema.sql, миграции 002/003/004 и вымышленные
frontend-фикстуры. SQL-схема не изменена. Тестовый `database/compose.test.yml`
не используется и не изменён. Порты PostgreSQL на хост не публикуются.

Backend: http://localhost:8000, Swagger: http://localhost:8000/docs.
React: http://localhost:5173. В frontend задать API base URL `http://localhost:8000`.
Настройка Vite зависит от frontend-проекта; эта документация не вводит новый
frontend-контракт. Для React в отдельном контейнере адрес backend внутри сети
нужно согласовать отдельно; код браузера использует адрес хоста.

Demo не требует `.env`, ключа LLM и RAG-корпуса. Он принудительно задаёт AI_MODE=demo
и пустую конфигурацию провайдера. Все POST анализа возвращают 503 с кодом
`AI_DISABLED_IN_DEMO` до обращения к AI или записи запуска в БД, даже если ключ
случайно попал в окружение процесса. Успешные ответы существующих API не менялись.
Новый POST /api/companies/{source_id}/news/{news_id}/analyses тоже заблокирован.
Внутренние demo-реквизиты PostgreSQL открыты в Compose и служат только для
изолированной локальной тестовой БД, не production.

`/health` по-прежнему проверяет жизнеспособность. В demo `/ready` требует
доступности 13 таблиц; false у `checks.rag` и `checks.llm_config` ожидаемы и не
мешают чтению профилей/инсайтов. В full `/ready` требует также RAG и настройки LLM;
проверка не вызывает провайдера и не доказывает действительность ключа.

## Данные и проверка API

Только вымышленные записи, не результат настоящего AI:

| source_id | Содержимое |
|---|---|
| DEMO-001 | Пекарня, два завершённых инсайта |
| DEMO-002 | Мастерская, один завершённый инсайт |
| DEMO-003 | Компания с пустой историей |

Каждая карточка содержит синтетические риски, возможности, рекомендации,
validation и явную пометку о вымышленном evidence. Confidence, impact и score не
выдумываются. Это тестовые данные интерфейса, не аналитические доказательства.

Открыть в браузере или вызвать `curl` (`curl.exe` в Windows PowerShell):

```sh
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl http://localhost:8000/api/companies/DEMO-001
curl "http://localhost:8000/api/companies/DEMO-001/insights?limit=1"
curl http://localhost:8000/api/companies/DEMO-001/insights/1
```

Идентификатор карточки получать из ленты; `1` верен для чистого первого запуска.
Проверка всего сценария без локального Python:

```sh
docker compose -p pulse-frontend-demo -f compose.frontend.yml --profile checks run --rm smoke
```

Smoke проверяет профили и Decimal, ленту/карточку, пагинацию, пустую историю,
приём синтетической новости через POST /api/news, дубликат и demo-политику,
изоляцию компаний, 404/422, CORS, /ready, OpenAPI и блокировку всех пяти POST AI.
При full или непустой LLM-конфигурации он отказывается выполнять POST-проверки.
`--rm` удаляет только создаваемый одноразовый smoke-контейнер.

## Порт и CORS

Разрешённые origins задаются через CORS_ORIGINS, разделитель — запятая. Без wildcard,
куки не включены; Authorization и Content-Type разрешены. Например, в PowerShell:

```powershell
$env:BACKEND_PORT='8001'
$env:CORS_ORIGINS='http://localhost:5173,http://127.0.0.1:5173'
docker compose -p pulse-frontend-demo -f compose.frontend.yml up -d --build --wait
```

В bash: `BACKEND_PORT=8001 CORS_ORIGINS=http://localhost:5173 docker compose ...`.
Smoke запускается внутри Docker, поэтому изменение внешнего порта ему не мешает.

## Full: явное включение настоящего AI

Full не включается одним изменением AI_MODE на хосте: нужен override-файл.
Создать локальный `.env.frontend.full` (Git его игнорирует):

```dotenv
LLM_API_KEY=REPLACE_LOCALLY
LLM_BASE_URL=https://YOUR_PROVIDER_ENDPOINT
LLM_MODEL=YOUR_MODEL
RAG_CORPUS_DIR=/absolute/path/to/permitted/prepared-json
CORS_ORIGINS=http://localhost:5173
```

В Windows использовать абсолютный путь вида `C:/private/pulse-rag`. Каталог должен
существовать и быть доступен Docker Desktop; bind mount read-only, автоматическое
создание отсутствующего пути запрещено. Корпус передаётся через закрытый канал
команды со сверкой SHA-256, см. BACKEND_SETUP.md. Закрытые PDF/JSON и .env
исключены из build context allowlist и в образ не копируются.

```sh
docker compose --env-file .env.frontend.full -p pulse-frontend-demo -f compose.frontend.yml -f compose.frontend.full.yml up -d --build --wait --wait-timeout 180
```

Запуск контейнеров и /ready не обращаются к LLM. POST анализа в full может быть
платным: вызывать его только при отдельном разрешении. Full использует ту же
локальную demo-БД; production DATABASE_URL не передаётся из окружения хоста.
Изоляция и фикстуры остаются тестовыми. Для отдельной full-БД используйте другой
project `-p pulse-frontend-full` и свободный BACKEND_PORT.
OCR/Tesseract в образ не включён: runtime использует подготовленные JSON.

Вернуться в demo: повторить базовую команду без override. Не запускать smoke
с full override. Не передавать реальные значения окружения в отчётах или
публиковать вывод `docker compose config` для full: он содержит ключ.

## Остановка и очистка только этого окружения

Посмотреть состояние и логи (сначала убедиться, что выбран нужный project):

```sh
docker compose -p pulse-frontend-demo -f compose.frontend.yml ps
docker compose -p pulse-frontend-demo -f compose.frontend.yml logs --tail 100 backend postgres
docker compose -p pulse-frontend-demo -f compose.frontend.yml stop
```

Stop сохраняет данные. При повторном запуске фикстуры не загружаются повторно:
initdb-скрипты работают только на пустом томе. Для явного применения 004 после
preflight и backup см. [NEWS_IDENTITY_MIGRATION.md](NEWS_IDENTITY_MIGRATION.md).
Автомиграция существующей БД
после будущих изменений схемы в этот сценарий не входит.

Следующая команда **не выполняется автоматически**. Только если вы намеренно
хотите удалить локальные тестовые данные проекта `pulse-frontend-demo`, сначала
проверьте его контейнеры и тома:

```sh
docker ps -a --filter label=com.docker.compose.project=pulse-frontend-demo
docker volume ls --filter label=com.docker.compose.project=pulse-frontend-demo
docker compose -p pulse-frontend-demo -f compose.frontend.yml down --volumes
```

Она удаляет контейнеры/сеть и именованные demo-тома только указанного project.
Не используйте её для чужого project. Внешний RAG bind-каталог не удаляется.
Не применять `docker system prune`, `docker volume prune` или массовое удаление.
При ошибке первой инициализации остановиться и изучить postgres logs; не считать
повторный запуск частично созданного тома успешной чистой инициализацией.

## Ограничения командной интеграции

JWT ещё не подключён; окружение предназначено для локальной разработки, backend
слушает только 127.0.0.1. Парсер, идемпотентность и очередь отсутствуют. Общие
FastAPI/lifespan, авторизация и CORS требуют согласования перед объединением.
Базовые теги Python/PostgreSQL обновляемые; зависимости Python закреплены в
requirements, но побитовая воспроизводимость образа не гарантируется.


## Обновление v1.15.0

Новый пустой demo-том применяет также 005 перед синтетическими данными (всего 15 таблиц). Существующий том не изменяется автоматически; безопасная ручная процедура — [ANALYSIS_JOBS.md](ANALYSIS_JOBS.md). Smoke проверяет OpenAPI v1.15.0 и demo-блокировку всех AI POST. Защищённый POST сохранённой новости в full возвращает 201/200/409; frontend должен учитывать новый 200 для replay и 409 для RUNNING/retry.
