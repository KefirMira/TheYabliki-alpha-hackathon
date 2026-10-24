# Автономный RSS-коллектор — v1.16.0

По умолчанию компонент читает **локальный синтетический RSS 2.0 XML**; HTTP RSS требует явного opt-in. Он отправляет публикации
только в `POST /api/news` на loopback backend. Он не импортирует backend, не
использует PostgreSQL, LLM, RAG или Docker. Локальная SQLite хранит очередь,
состояние источников, журнал попыток и результаты доставки.

## Установка и запуск в Windows

Python 3.12. Команды выполнять из корня репозитория, где находятся backend/ и parser/.
Отдельное окружение не требует зависимостей backend:

```powershell
py -3.12 -m venv .venv-parser
.\.venv-parser\Scripts\python.exe -m pip install -r parser/requirements.txt
.\.venv-parser\Scripts\python.exe -m pip check
.\.venv-parser\Scripts\python.exe -m parser --once
```

После активации этого окружения эквивалентная команда — `python -m parser --once`.
Backend должен быть запущен отдельно. По умолчанию используется локальный demo
`http://127.0.0.1:8000`; коллектор не запускает и не изменяет его конфигурацию.
Для тестов не нужны ни этот backend, ни Docker: используется подставной HTTP-сервер.

Первый запуск ставит в очередь пять корректных записей. Доставленные записи
повторно не отправляются; при неопределённом результате повтор защищает дедупликация backend.
Остальные пять
элементов фикстуры пропускаются с диагностикой. В demo это маркированные
`synthetic-demo`, `SYNTH-*` и `example.invalid`. Реальные тексты нельзя маскировать
этой маркировкой. Проверка значения идентификаторов не доказывает синтетичность текста.

## Конфигурация

Только переменные процесса, без автоматической загрузки `.env` и без настроек backend.

| Переменная | По умолчанию | Значение |
|---|---|---|
| PARSER_RSS_PATH | fixtures/synthetic.xml | Только локальный UTF-8/UTF-8 BOM файл, максимум 1 MiB |
| PARSER_REPORT_PATH | reports/last-run.json | JSON-отчёт с результатами одного запуска |
| PARSER_BACKEND_URL | http://127.0.0.1:8000 | HTTP/HTTPS origin: только localhost, 127.0.0.1 или ::1, без credentials/path/query/fragment |
| PARSER_SOURCE_NAME | synthetic-demo | Стабильный технический ID, 1–100 символов `[a-z0-9._-]` |
| PARSER_HTTP_TIMEOUT | 10 | Таймаут HTTP в секундах, больше 0 и не больше 60 |
| PARSER_STATE_PATH | state/parser.sqlite3 | Приватная SQLite; отдельный файл .sqlite3/.sqlite/.db |
| PARSER_MAX_ATTEMPTS | 5 | Общее число попыток, включая первую; 1–20 |
| PARSER_BACKOFF_BASE | 2 | Начальная задержка, 0.01–3600 секунд |
| PARSER_BACKOFF_CAP | 300 | Верхняя граница backoff, от base до 86400 секунд |
| PARSER_POLL_INTERVAL | 30 | Интервал обхода в --poll, 0.01–86400 секунд |
| PARSER_REQUEST_INTERVAL | 0.2 | Минимальное расстояние между началами запросов, 0.001–60 секунд |
| PARSER_LEASE_SECONDS | 180 | Lease источника; не меньше timeout + request_interval + 10, максимум 86400 секунд |

Относительные файловые пути считаются от parser/, независимо от cwd. В CLI всё
равно нужно находиться в корне репозитория для импорта `python -m parser`.
Пример изменения внешнего порта локального backend:

```powershell
$env:PARSER_BACKEND_URL='http://127.0.0.1:8001'
$env:PARSER_REPORT_PATH='reports/my-run.json'
.\.venv-parser\Scripts\python.exe -m parser --once
```

source_name берётся из конфигурации, не из channel/title. В demo backend разрешён
только `synthetic-demo`; для согласованного внешнего источника нужен отдельный технический идентификатор.
Локальный адаптер сохраняет прежнюю политику синтетических данных. HTTP RSS описан ниже; ссылки статей, изображения и namespace URI не скачиваются. Backend-client не следует редиректам. Proxy из окружения не используется.

## Преобразование RSS

- Поддерживается RSS 2.0, не Atom. DTD/entities запрещены; XML разбирается локально.
- title очищается до текста. Без него элемент пропускается.
- content:encoded предпочтительнее description; при пустом результате используется
  description. При отсутствии обоих текст не подменяется заголовком.
- HTML превращается в текст: теги/атрибуты/комментарии удаляются, block-теги
  разделяются пробелами, HTML entities декодируются. script/style/iframe/object/
  template/head/svg/noscript вместе с содержимым подавляются. Код не исполняется.
  Результат — plain text, его нельзя считать разрешением для frontend innerHTML.
- Если description содержит только анонс, именно анонс и становится content.
  Полная статья не загружается и полнота текста не заявляется.
- guid передаётся как source_id с сохранением регистра; padded GUID отклоняется.
  Без guid допустим корректный link. Без link и guid элемент не отправляется.
- pubDate читается как RFC 822 либо ISO 8601 с timezone и переводится в UTC.
  Отсутствующая дата остаётся NULL. Некорректная/naive дата тоже становится NULL,
  но добавляется INVALID_PUBDATE. Время обхода никогда не подставляется.
- Не проходят валидацию: title свыше 500, content свыше 100000, URL свыше 2048,
  source_id свыше 500, language свыше 10 символов, пустой текст и NUL.
  Контракт описан в [NEWS_INGESTION_API.md](../docs/NEWS_INGESTION_API.md).
- URL не канонизируется повторно: удалением tracking и дедупликацией владеет backend.

Некорректный элемент не мешает обработке следующих. Некорректный XML целиком,
запрещённый DTD, слишком большой/недоступный файл не продвигают успешное состояние
источника; уже сохранённая очередь всё равно обрабатывается.

## SQLite, повторы и перезапуск

Все подготовленные элементы одного обхода сохраняются одной транзакцией
`BEGIN IMMEDIATE` с `synchronous=FULL` и WAL. Только после её COMMIT отдельная
транзакция фиксирует успешный обход и ETag/Last-Modified. При сбое между ними
очередь уже на диске, а следующий обход безопасно повторяет постановку.
При ошибке внутри пакетной постановки откатывается весь пакет и checkpoint не меняется.

Уникальность очереди: `source_name + (guid либо URL)`, с отдельными префиксами
для GUID и URL. Дата и хеш текста не используются. URL сохраняется как получен;
его канонизацией владеет backend. Варианты tracking URL без GUID могут создать
разные элементы очереди, но backend объединит их по каноническому URL.
Изменённый payload прежней публикации не заменяет первый: сохраняется
`LOCAL_PAYLOAD_CHANGED` для ручного разбора. Доставленные записи не переотправляются.

Состояния: pending → inflight → delivered / retry / failed / dead_letter.
Попытка фиксируется **перед** HTTP; её результат, news_id и diagnostics сохраняются
после ответа одной транзакцией. После падения inflight становится retry (или
dead_letter при исчерпании лимита), в журнале остаётся `uncertain`.
Это доставка с возможными повторами, а не распределённая exactly-once транзакция.
Для каждой записи сохраняется первоначальный payload и история попыток.

timeout, сетевые ошибки, 429, 500/502/503/504 повторяются ограниченно.
Для попытки N задержка: `min(cap, base * 2^(N-1)) * uniform(0.5, 1)`.
Retry-After (секунды либо HTTP-date с timezone) задаёт дополнительную нижнюю
границу и общий cooldown backend; поэтому фактическая задержка может превышать cap.
Неверный Retry-After игнорируется. 409/422 и прочие постоянные ошибки → failed,
исчерпание попыток → dead_letter. Ничего автоматически не удаляется.
Невалидный ответ 200/201 не считается успехом и требует ручной проверки.

Lease источника в SQLite запрещает одновременный обход одного source_name
процессами с **одним и тем же файлом состояния**. Продление проверяет владельца;
просроченный процесс не может завершить результат от имени нового владельца.
Rate limit сохраняется для backend origin и общий для процессов с этой SQLite.
Не запускайте независимые state-файлы для одного логического источника.
SQLite предназначена для локального диска, не сетевой файловой системы.

ETag/Last-Modified сохраняются только после надёжного enqueue. HTTP 304 не очищает очередь и не мешает доставке ожидающих элементов; отсутствующие валидаторы 304 сохраняют прежние значения. HTTP 200 без валидатора удаляет старый валидатор.

Путь состояния должен принадлежать одному логическому backend. После удаления
demo-БД не используйте старые delivered/news_id как подтверждение данных новой БД.
Для независимого нового demo укажите новый PARSER_STATE_PATH, сохранив прежнюю
SQLite для диагностики. Автоматического сброса/повторной постановки failed нет.
Для чтения после остановки коллектора можно открыть SQLite стандартным sqlite3:
`SELECT id,status,attempts,news_id,last_error FROM queue ORDER BY id;`.
Файлы SQLite, WAL/SHM/journal, state/ и reports/ исключены из Git; они содержат
payload и требуют такого же контроля доступа, как локальные входные данные.

## Постоянный запуск и остановка

```powershell
$env:PARSER_POLL_INTERVAL='10'
$env:PARSER_STATE_PATH='state/parser.sqlite3'
.\.venv-parser\Scripts\python.exe -m parser --poll
```

Ctrl+C / SIGTERM устанавливает флаг остановки: ожидания прерываются, текущий
HTTP-запрос завершается в пределах настроенных сетевых таймаутов, затем SQLite
и HTTP-клиент закрываются. Lease освобождается. После аварийного завершения
следующий процесс ждёт истечения lease, затем восстанавливает inflight.
--once выполняет один обход и не более одной попытки для каждого готового элемента;
ожидает только краткое rate spacing, а не будущий backoff/длинный Retry-After.
--poll повторяет обход/доставку с интервалом, поэтому retry может произойти позже
своего deadline на один интервал polling. Для продолжения используйте тот же state-файл.

## Результаты и HTTP-ошибки

| Ответ/событие | status в отчёте |
|---|---|
| 201 | created, сохранён news_id |
| 200 | duplicate, сохранены news_id и diagnostics |
| 409 | conflict / NEWS_IDENTITY_CONFLICT |
| 422 | invalid_data / REQUEST_VALIDATION_ERROR |
| 503 | unavailable / BACKEND_TEMPORARY_ERROR |
| 429 | rate_limited, Retry-After учитывается |
| 500/502/504 | temporary_error |
| 403 | forbidden / BACKEND_ACCESS_DENIED |
| Timeout | timeout |
| Сетевая ошибка | network_error |
| Некорректный успешный ответ | invalid_response |
| Другой HTTP-статус | http_error |

Каждый готовый элемент отправляется не более одного раза за запуск. Временные ошибки
планируют следующую попытку в SQLite; остальные элементы продолжают обрабатываться,
если backend не назначил общий Retry-After. raw response body
не выводится; диагностика не содержит текстов публикаций и значений секретов.

JSON печатается в stdout и атомарно записывается в PARSER_REPORT_PATH. Содержит
queue_id, source_id, статус последнего вызова, queue_status, attempts,
next_attempt_at (UTC Unix timestamp), news_id, diagnostics, предупреждения и счётчики.
Для доставленных ранее — already_delivered. Пропущенные элементы имеют исходный
item index. Источник, занятый другим процессом, возвращает source_busy без обхода.
Файл last-run.json заменяется; долговременные данные находятся в SQLite.

Exit codes --once: 0 — нет недоставленных элементов (или источник занят);
1 — есть ожидающие, failed либо dead_letter; 2 — ошибка конфигурации/файла/XML/записи отчёта
либо аргументов CLI. Пропущенные элементы отражаются в отчёте и сами по себе не
меняют код на 1. При потере HTTP-ответа запись уже могла сохраниться: повторную
доставку безопасно идентифицирует backend по паре/URL, не по текстовому хешу.

--poll продолжает работу при ошибках источника/доставки и возвращает 0 после
штатной остановки; ошибка SQLite/конфигурации/записи отчёта завершает процесс с 2.

## Тесты без PostgreSQL, LLM и реальных источников

```powershell
.\.venv-parser\Scripts\python.exe -m pip install -r parser/requirements-test.txt
.\.venv-parser\Scripts\python.exe -m pytest parser/tests -q
```

Всегда указывать parser/tests. Не запускать вручную backend/test_*.py — это старые
скрипты с OCR и вызовами провайдера. Корневой pytest.ini выбирает безопасные
backend/tests и parser/tests; отдельного parser pytest-конфига нет. В тестах
коллектора dotenv отключён, LLM-переменные удаляются и импорт SDK блокируется
уже при коллекции. Сетевой guard блокирует DNS/connect вне loopback, включая CLI
подпроцессы через тестовый sitecustomize. SQLite-файлы создаются в tmp_path.
Чистое окружение парсера вообще не содержит LLM/PostgreSQL-зависимостей;
sqlite3 входит в стандартную библиотеку Python, новых pip-зависимостей нет.

Тесты используют вымышленные XML, httpx MockTransport и локальный подставной HTTP
backend на случайном порту. Проверяются статусы, продолжение после ошибок,
повторная доставка с прежними ID, diagnostics, даты, HTML и настоящий запуск CLI
через `python -m parser --once`. Не подключать тесты к общей БД или настоящим RSS.

## Ограничения

Нет Docker-сервиса parser, сопоставления компаний и AI-вызовов.
Один процесс обрабатывает элементы последовательно. Перед реальными источниками
нужны отдельный этап, проверка условий использования, авторизация backend и
согласование источников. Нет административного API для ручного requeue и очистки
архива; delivered/failed/dead_letter накапливаются, JSON-отчёт содержит всю очередь
текущего источника. Политика retention и работа с большими объёмами — следующий этап.
Backend ограничен loopback; HTTP RSS не является способом обхода условий источника.


## HTTP RSS v1.16.0: по умолчанию отключён

Кандидат и результат проверки условий: [SOURCE_REVIEW.md](SOURCE_REVIEW.md). Источник Банка России **не включён**: разрешение для нашего сценария и robots.txt не подтверждены. Встроенного реального URL нет. Сначала согласуйте источник, атрибуцию, частоту и условия использования. Не используйте robots.txt как замену разрешению правообладателя.

| Переменная | По умолчанию | Значение |
|---|---|---|
| PARSER_SOURCE_MODE | local | local или http |
| PARSER_HTTP_RSS_ENABLED | 0 | HTTP требует явного 1; само по себе не подтверждает разрешение источника |
| PARSER_RSS_URL | отсутствует | Явный HTTP(S) RSS URL, без credentials/fragment; порты только 80/443 |
| PARSER_SOURCE_NAME | synthetic-demo | В http должен быть явно задан стабильный lowercase ASCII technical ID |
| PARSER_SOURCE_INTERVAL | 300 | Минимальный промежуток между обходами, секунды, 1–86400; реальный интервал согласуется с источником |
| PARSER_RSS_MAX_BYTES | 1048576 | Лимит XML 1..1048576 байт |
| PARSER_RSS_MAX_REDIRECTS | 3 | 0–5; только тот же scheme/host/port |

PARSER_HTTP_TIMEOUT (10 секунд, максимум 60) применяется и к RSS. DNS ожидание ограничено, одновременно не более двух незавершённых OS DNS-операций. Все DNS-адреса должны быть публичными: private, loopback, link-local, multicast, reserved, IPv4-mapped IPv6 запрещены. TCP использует проверенный IP, HTTPS сохраняет исходный hostname для SNI/проверки сертификата. На каждом редиректе DNS проверяется заново; переход на другой origin, downgrade и redirect loop отклоняются. Proxy/cookies/Authorization не используются. Сжатые ответы запрещены (Accept-Encoding: identity), чтобы исключить decompression bomb. Ограничиваются байты и длительность чтения, включая медленные заголовки.

Поддерживаются RSS 2.0, UTF-8/BOM, windows-1251, ISO-8859-1 и ASCII. Конфликт HTTP charset и XML declaration, повреждённые байты, неизвестная кодировка, DTD/entities и невалидный XML отклоняются без checkpoint. Atom/UTF-16 не поддерживаются. Никакой загрузки полных статей: description/content:encoded — весь доступный текст, иногда только анонс. Заголовок не подставляется вместо content. GUID очищается от крайних пробелов с сохранением регистра; при отсутствии GUID используется URL. Без GUID и URL элемент пропускается. Невалидная дата остаётся null с INVALID_PUBDATE; время обхода её не заменяет.

### Изолированный HTTP-сценарий без сети, backend и LLM

```powershell
# Из корня репозитория; зависимости — parser/requirements.txt.
$fixtureState = Join-Path $env:TEMP 'pulse-http-rss-fixture-v116'
.\.venv-parser\Scripts\python.exe -m parser.offline_http_demo --once --state-dir $fixtureState
# Повтор: те же SQLite/checkpoints, уже доставленные публикации не посылаются снова.
.\.venv-parser\Scripts\python.exe -m parser.offline_http_demo --once --state-dir $fixtureState
```

Это явный fake transport, не опция отключения SSRF-защиты production-клиента. DNS и оба HTTP-направления подставные. Используется существующая синтетическая XML-фикстура: HTTP-адаптер принимает 6 идентичностей (включая GUID с убранными крайними пробелами); локальный адаптер по-прежнему принимает прежние 5. demo создаёт только приватную SQLite и отчёт в указанной папке. Объекты news_id в нём синтетические и не принадлежат настоящей БД.

### Подготовка согласованного источника (не запускать до одобрения)

```powershell
$env:PARSER_SOURCE_MODE = 'http'
$env:PARSER_HTTP_RSS_ENABLED = '0' # оставить 0 до согласования
$env:PARSER_RSS_URL = 'https://approved-feed.example.invalid/rss'
$env:PARSER_SOURCE_NAME = 'approved-source'
$env:PARSER_STATE_PATH = Join-Path $env:TEMP 'pulse-approved-rss/queue.sqlite3'
$env:PARSER_REPORT_PATH = Join-Path $env:TEMP 'pulse-approved-rss/report.json'
$env:PARSER_SOURCE_INTERVAL = '300'
```

После разрешения укажите подтверждённый URL и частоту, установите enable=1 и выполните `python -m parser --once` вручную. Backend должен быть изолированным loopback-получателем POST /api/news без LLM-ключей; demo допускает только синтетические публикации, реальные в него отправлять нельзя. Режим full и доступ к его платным маршрутам требуют отдельной политики доступа. Никакой автоматический AI или POST анализа parser не выполняет. `--poll` включается только явной командой после отдельного согласования, не стартует вместе с frontend demo.

### Checkpoints, ошибки, конкуренция

SQLite v1 автоматически обновляется до v2 транзакционным добавлением трёх колонок sources: fetch_failures, fetch_blocked, next_fetch. Очередь, журнал доставки, validators и news_id сохраняются. Перед обновлением остановите старые процессы и сохраните резервную копию приватного состояния; downgrade на старый parser не поддерживается.

source_name привязывается к точному HTTP locator; смена URL требует отдельного source_name/state или согласованной миграции состояния, автоматического переноса validators нет. Владелец lease проверяется **внутри enqueue и checkpoint**; устаревший процесс после takeover не может изменить их. Enqueue всей пачки фиксируется раньше checkpoint. При сбое перед checkpoint очередь сохраняется, повторный RSS не дублирует её; rate deadline после аварии тоже сохраняется.

Timeout/network/429/5xx повторяются только в следующих запусках, без внутренних HTTP retry. Exponential backoff с jitter, cap и Retry-After (секунды/HTTP-date) сохраняются в SQLite, отдельно от backend-delivery retries. Минимальный source interval имеет приоритет, если он больше backoff. Максимум PARSER_MAX_ATTEMPTS (default 5) последовательных ошибок получения; затем source блокируется. Ошибки XML/кодировок/политики/небезопасных адресов блокируют сразу. Даже blocked/deferred source продолжает доставлять уже сохранённую очередь.

После устранения причины вручную: `python -m parser --once --reset-source-errors`. Команда только для HTTP --once, сохраняет очередь, validators и оставшийся Retry-After/rate deadline; авто-сброс при polling запрещён. Report содержит source_fetch_status, fetch_failures/fetch_blocked/next_fetch и безопасные коды ошибок. В HTTP-отчёте GUID скрыт (`source_id=null`, identity_digest=SHA-256 ключа); точный GUID остаётся только в приватной SQLite и payload. Тела RSS, URL с query, validators и тексты сетевых исключений в stdout/stderr не печатаются. Локальные отчёты сохраняют прежний формат source_id.

Backend и миграции PostgreSQL 001–005 не меняются. Выпуск v1.16.0 относится к parser; версия backend OpenAPI остаётся v1.15.0.

При редиректе на другой path validators не пересылаются и не сохраняются для исходного URL: это предотвращает ложный 304 для другой публикации. Для эффективного ETag-кэширования задавайте согласованный конечный RSS URL без редиректа. IPv6 6to4/Teredo также блокируются.


## Результаты проверки v1.16.0

Полный безопасный прогон backend + parser: **445 passed, 0 skipped**. Из них 160 тестов parser. Внешняя сеть и SDK LLM заблокированы; используются fake RSS/DNS, синтетический XML и loopback HTTP. PostgreSQL 16.15: SQL-runner, replay 002–005 и контрольные суммы — успешно; миграции и backend не изменены. Прежнее предупреждение Starlette/httpx не связано с parser.

Docker smoke существующего frontend demo — успешно; сервис parser отсутствует, AI POST заблокированы. Использованы локальные зависимости и read-only текущий backend с проверкой manifest, без новой сборки образа/загрузки пакетов. Сеть theyabliki-db-check-1a832d244c5f_default повторно использована, PostgreSQL-тома новые и отдельные. Созданные контейнеры остановлены; сети, тома и чужие ресурсы не удалялись. Реальный RSS и периодический внешний сбор не включены.
