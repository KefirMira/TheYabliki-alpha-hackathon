# PostgreSQL для «Пульса бизнеса»

Только схема, миграции и полностью синтетические фикстуры. Реальные CSV и оригинальный seed.sql в Git не включаются; для них потребуется отдельный импорт.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File database/tests/run.ps1
```

Скрипт проверяет 13 таблиц, FK, ограничения, повтор миграций и хранение AI-ответа без LLM. Создаёт отдельный PostgreSQL 16 и останавливает его с сохранением тома.
Подробности: [DATABASE_HANDOFF.md](../docs/DATABASE_HANDOFF.md).
