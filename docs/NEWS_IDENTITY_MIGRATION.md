# Проект миграции 004: идентичность внешних новостей

Статус: замечания архитектурного ревью учтены, локальная версия v1.10.0. НЕ разрешение на применение
к общей/production-БД. POST /api/news пока не реализован. Миграция проверяется
только на изолированной PostgreSQL 16 с синтетическими данными.

## Порядок применения

`database/schema.sql` → `002_pulse_features.sql` → `003_integrity.sql` →
`004_news_external_identity.sql`. Файла 001 в репозитории нет: исходная схема —
schema.sql. Журнала версий миграций нет; существующие PowerShell runners вызывают
SQL через psql с `ON_ERROR_STOP=1` и повторяют миграции для проверки совместимости.

004 не добавляет таблиц/колонок, не меняет FK и API. Она добавляет два CHECK
на существующие колонки и один частичный уникальный индекс:

- `news_external_source_name_check`: для EXTERNAL значение source_name либо NULL,
  либо непустая lowercase ASCII-строка из `[a-z0-9._-]`. COLLATE "C" фиксирует
  интерпретацию диапазонов. NULL означает отсутствие идентификатора.
- `news_external_source_id_check`: для EXTERNAL значение source_id либо NULL,
  либо непустая строка без начального/конечного ASCII whitespace (POSIX space
  с COLLATE "C": пробел, tab, CR/LF, form feed, vertical tab). Регистр и внутренние
  символы не меняются. Unicode-ID не запрещены; Unicode whitespace вне этой
  группы данный CHECK не классифицирует. Это нужно учесть в API-валидации.
- `uq_news_external_source_identity`: UNIQUE (source_name COLLATE "C", source_id COLLATE "C") для
  EXTERNAL с обоими непустыми значениями, независимо от URL.

MANUAL не попадает под новые CHECK и уникальность пары. Существующий URL UNIQUE
и неуникальный content_hash сохраняются. Пропущенные компоненты пары допускаются;
в этом случае гарантии идентичности пары нет.

## Предварительная проверка целевой БД

Выполнять только чтение; при конфликтах не исправлять и не удалять строки
автоматически. Не публиковать тексты новостей/внешние ID из рабочей БД в логах.

```sql
SELECT source_name COLLATE "C", source_id COLLATE "C", count(*)
FROM public.news_articles
WHERE input_kind='EXTERNAL'
  AND source_name IS NOT NULL AND source_id IS NOT NULL
  AND btrim(source_name)<>'' AND btrim(source_id)<>''
GROUP BY source_name COLLATE "C", source_id COLLATE "C"
HAVING count(*)>1;

SELECT id
FROM public.news_articles
WHERE input_kind='EXTERNAL' AND (
  (source_name IS NOT NULL AND NOT (source_name COLLATE "C" ~ '^[a-z0-9._-]+$'))
  OR (source_id IS NOT NULL AND
      (source_id='' OR source_id COLLATE "C" ~ '^[[:space:]]|[[:space:]]$'))
);
```

Дубликаты после предполагаемой нормализации также нужно изучить отдельно:
миграция намеренно НЕ выполняет lower/trim/update. Если источник раньше имел
разные написания, их обработка требует отдельного согласования с владельцем данных.

## Транзакционность и повторное применение

Весь файл выполняется в одной транзакции. `lock_timeout=10s`; явный
SHARE ROW EXCLUSIVE lock блокирует конкурирующие записи, но допускает обычные
SELECT. Добавление CHECK/создание индекса может потребовать более сильных locks,
поэтому применять только в согласованное окно обслуживания. Длительность
сканирования таблицы не ограничена lock_timeout; оценить её на копии данных.

До создания объектов проверяются существующие дубликаты; конфликт вызывает 23505.
Ненормализованные существующие значения отклоняются CHECK с 23514. Ошибка
откатывает все изменения файла; строки не переписываются.

Повторный запуск проверяет валидность и каноническое определение CHECK/индекса
через каталоги PostgreSQL, включая готовность и COLLATE "C" обоих ключей.
pg_get_indexdef может опустить COLLATE, совпадающий с collation колонки;
дополнительно проверяются фактические OID в pg_index.indcollation.
Если имя занято объектом
с другим определением, миграция завершается ошибкой, а не пропускает его через
IF NOT EXISTS. Сравнение намеренно строгое и ориентировано на PostgreSQL 16:
эквивалентный, но иначе записанный predicate тоже требует ревью, не автоисправления.

На общей БД после отдельного одобрения разработчика использовать psql с
`-X -v ON_ERROR_STOP=1 -f database/migrations/004_news_external_identity.sql`.
Не оборачивать файл дополнительной внешней транзакцией. После ошибки завершить
сессию либо выполнить ROLLBACK до дальнейших действий.

## Тесты без общей БД

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File database/tests/run.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File backend/tests/run-profile-tests.ps1 -DatabaseRoot '<текущий-checkout>/database'
```

Первый runner применяет 004 дважды, проверяет прежние 13 таблиц, ограничения и
контрольные суммы фикстур. Второй также повторяет 004, запускает backend-тесты и
передаёт отдельную тестовую DSN для тестов миграции. Каждый такой тест создаёт
свою UUID-БД внутри нового тестового сервера и удаляет только её после завершения.
Главная БД runner и её baseline не изменяются этими тестами. Для этого тестовому
пользователю нужны права CREATE DATABASE; production-реквизиты не использовать.

Проверяются пары и разные источники, MANUAL, неполные пары, регистр ID,
невалидные значения, гонка двух INSERT с разными URL, откат при плохих старых
данных, несовпадающие определения объектов, повтор и совместимость frontend seed.
Тесты не вызывают LLM. Созданные Compose-проекты останавливаются с сохранением
контейнеров и томов; чужие проекты не меняются.

Тестовый Compose уже монтирует migrations read-only. Frontend Compose для НОВОГО
пустого тома применяет schema → 002 → 003 → 004 → demo-фикстуры. Существующие тома
автоматически не мигрируются. Тесты получают NEWS_IDENTITY_DATABASE_ROOT из
фактически выбранного runner DatabaseRoot и читают schema/002/003/004 из него.
Старый checkout без 004 поддерживается как отдельный режим совместимости:
пропуск тестов 004 в нём не подтверждает готовность v1.10.0.

## Существующий demo-том: только явная процедура

Эти команды НЕ выполняются автоматически и НЕ предназначены для общей/production-БД.
Проверить, что выбран именно собственный project pulse-frontend-demo и база pulse_demo.
Не использовать down --volumes и не пересоздавать том. Остановить всех writers,
включая отдельные ingestion/worker процессы, если они существуют:

```sh
docker compose -p pulse-frontend-demo -f compose.frontend.yml ps
docker volume ls --filter label=com.docker.compose.project=pulse-frontend-demo
docker compose -p pulse-frontend-demo -f compose.frontend.yml stop backend
docker compose -p pulse-frontend-demo -f compose.frontend.yml exec -T postgres pg_dump -U pulse_demo -d pulse_demo -Fc -f /tmp/pulse-before004.dump
docker compose -p pulse-frontend-demo -f compose.frontend.yml cp postgres:/tmp/pulse-before004.dump ./pulse-before004.dump
docker compose -p pulse-frontend-demo -f compose.frontend.yml exec -T postgres pg_restore --list /tmp/pulse-before004.dump
docker compose -p pulse-frontend-demo -f compose.frontend.yml cp database/tests/news_identity_preflight.sql postgres:/tmp/news-preflight.sql
docker compose -p pulse-frontend-demo -f compose.frontend.yml exec -T postgres psql -X -v ON_ERROR_STOP=1 -U pulse_demo -d pulse_demo -f /tmp/news-preflight.sql
```

Убедиться, что backup получен и его каталог читается pg_restore --list; проверять
восстановление только в отдельной тестовой БД. Оба счётчика failures должны быть 0.
При конфликтах остановиться, не исправлять и не удалять строки автоматически.
Индекс старого проекта 004 без COLLATE C будет отклонён: замену согласовать отдельно.
После успешной проверки и согласования окна блокировки выполнить по очереди:

```sh
docker compose -p pulse-frontend-demo -f compose.frontend.yml cp database/migrations/004_news_external_identity.sql postgres:/tmp/004_news_external_identity.sql
docker compose -p pulse-frontend-demo -f compose.frontend.yml exec -T postgres psql -X -v ON_ERROR_STOP=1 -U pulse_demo -d pulse_demo -f /tmp/004_news_external_identity.sql
docker compose -p pulse-frontend-demo -f compose.frontend.yml exec -T postgres psql -X -v ON_ERROR_STOP=1 -U pulse_demo -d pulse_demo -f /tmp/004_news_external_identity.sql
docker compose -p pulse-frontend-demo -f compose.frontend.yml start backend
docker compose -p pulse-frontend-demo -f compose.frontend.yml --profile checks run --rm --no-deps smoke
```

При ненулевом exit code не выполнять следующую команду. При ошибке миграции
оставить writers остановленными и передать причину разработчику БД. Не заменять
объекты автоматически. Копирование SQL в /tmp поддерживает старый контейнер без
mount 004, не меняя его startup и не пересоздавая том. Эта процедура только
документирована; существующие demo-тома в ходе разработки не мигрировались.

## Откат после отдельного разрешения

Сначала остановить приём внешних новостей. В согласованное окно:

```sql
BEGIN;
SET LOCAL lock_timeout='10s';
DROP INDEX public.uq_news_external_source_identity;
ALTER TABLE public.news_articles
  DROP CONSTRAINT news_external_source_id_check,
  DROP CONSTRAINT news_external_source_name_check;
COMMIT;
```

Данные сохраняются, но гарантии нормализации и уникальности пары снимаются.
Объекты с неожиданными определениями не удалять без отдельного выяснения причин.
Прежде чем повторно включать ingestion, согласовать совместимую версию backend.

## За рамками 004

Канонизация URL и поиск конфликтов двух ключей относятся к будущему backend
приёма. Миграция не нормализует URL, не объединяет публикации и не хранит алиасы.
При одинаковом URL и разных внешних ID потребуется диагностика; когда пара
указывает на одну строку, а URL на другую — отдельный ответ конфликта.
