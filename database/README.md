# PostgreSQL для «Пульса бизнеса»

Только схема, миграции и полностью синтетические фикстуры. Реальные CSV и оригинальный seed.sql в Git не включаются; для них потребуется отдельный импорт.

Приватный CSV профилей компаний: [dry-run и безопасный импорт](../docs/COMPANY_CSV_IMPORT.md).
Платежи и связи SYNTHETIC_F этим инструментом не импортируются.

Отдельный импорт строк платежей и непрозрачных связей идентификаторов:
[DATASET_CSV_IMPORT.md](../docs/DATASET_CSV_IMPORT.md). Сохранение повторов без
суммирования; реальные файлы пока проверены только через dry-run.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File database/tests/run.ps1
```

Скрипт проверяет 18 таблиц, FK, ограничения, повтор миграций и хранение AI-ответа без LLM. Создаёт отдельный PostgreSQL 16 и останавливает его с сохранением тома.
Подробности: [DATABASE_HANDOFF.md](../docs/DATABASE_HANDOFF.md).

Проект миграции 004 и порядок ревью/применения:
[NEWS_IDENTITY_MIGRATION.md](../docs/NEWS_IDENTITY_MIGRATION.md).
Новые Docker demo-базы применяют schema → 002 → 003 → 004 → 005 → 006 перед фикстурами.
Существующие тома автоматически не мигрируются; явная процедура с preflight
и backup описана в NEWS_IDENTITY_MIGRATION.md. Общая БД требует отдельного разрешения.

Сопоставление компаний без AI, миграция 006 и локальный CLI:
[NEWS_COMPANY_MATCHING.md](../docs/NEWS_COMPANY_MATCHING.md).
