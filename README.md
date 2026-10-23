# TheYabliki-alpha-hackathon
Репозиторий команды TheYabliki для хакатона Альфа Банк

Backend для frontend без установки Python: [Docker demo/full и smoke-проверки](docs/FRONTEND_DOCKER.md).

Контракт парсера: [POST /api/news](docs/NEWS_INGESTION_API.md) — приём без запуска AI.

Следующий шаг: [анализ сохранённой новости для компании](docs/SAVED_NEWS_ANALYSIS_API.md).

PostgreSQL 16 для «Пульса бизнеса»: [запуск и передача БД](docs/DATABASE_HANDOFF.md).
Изолированные проверки: `powershell -NoProfile -ExecutionPolicy Bypass -File database/tests/run.ps1`.
