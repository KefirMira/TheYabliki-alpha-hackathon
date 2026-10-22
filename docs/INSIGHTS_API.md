# Лента и карточка инсайтов — v1.8.0

Чтение выполняется только из PostgreSQL, без RAG, AI и LLM. SQL-схема и миграции PR №2 не меняются; инфраструктура берётся из отдельного checkout через DatabaseRoot.

## Лента

`GET /api/companies/{source_id}/insights?limit=20&cursor=<token>`

limit: 1–100, по умолчанию 20. Для первой страницы cursor не передавать. Ответ:

```json
{
  "items": [
    {
      "insight_id": 51,
      "run_id": 42,
      "company_id": "SYNTH-COMPANY-A",
      "type": null,
      "relevance": "high",
      "summary": "Synthetic summary",
      "created_at": "2026-10-22T10:20:30.123456Z",
      "status": "COMPLETED"
    }
  ],
  "next_cursor": null
}
```

Пример синтетический. type берётся из insight_kind, relevance из relevance_level, summary из impact_summary. Неизвестные значения остаются null. Тип не выводится автоматически из наличия рисков или возможностей. created_at — дата создания результата анализа, а не публикации новости или документа. status — статус выполнения analysis_runs, а не подтверждение прогноза или достоверности.
Возвращаются только строки с COMPLETED. Для известной компании без завершённых результатов ответ 200 с items=[] и next_cursor=null.

## Курсор

Сортировка: created_at DESC, id DESC. Используется keyset-pagination с условием (created_at, id) < позиции курсора, без OFFSET. Запрашивается limit+1 строка; следующий курсор строится по последнему возвращённому элементу только при наличии продолжения.
Курсор — base64url JSON версии 1 с компанией, timezone-aware датой (с микросекундами) и положительным BIGINT id. Фронтенд передаёт полученный токен без изменений. Он не содержит секретов и не является средством авторизации. SQL всегда самостоятельно ограничивает компанию и COMPLETED.
Некорректное кодирование, неизвестная версия, дата без timezone, неверный id и курсор другой компании дают 422. Курсор фиксирует позицию, а не снимок всей БД: новая запись в начале ленты не сдвигает продолжение. При административном изменении created_at уже существующих строк порядок может измениться; приложение дату создания не обновляет.

## Карточка

`GET /api/companies/{source_id}/insights/{insight_id}`

```json
{
  "insight_id": 51,
  "run_id": 42,
  "company_id": "SYNTH-COMPANY-A",
  "type": null,
  "relevance": "high",
  "summary": "Synthetic summary",
  "created_at": "2026-10-22T10:20:30.123456Z",
  "status": "COMPLETED",
  "news": {"id": 36, "title": "Synthetic news", "text": "Synthetic history news"},
  "risks": ["Synthetic risk"],
  "opportunities": [],
  "recommendations": ["Synthetic action"],
  "validation": {"passed": false, "warnings": ["Synthetic warning"]},
  "sources": [
    {"id": 1, "document": "synthetic-month.pdf", "page": 2, "chunk_id": 3, "date": "2026-08", "score": 0.42}
  ],
  "evidence": [
    {"id": 61, "evidence_type": "PDF", "text": "Exact synthetic retrieval fragment.\nSecond line.", "document": "synthetic-month.pdf", "page": 2, "chunk_id": 3, "document_date": null}
  ]
}
```

Это условный пример формы ответа. Источники берутся из source_snapshot без изменения исходной точности даты; доказательства — из insight_evidence с сохранённым текстом. Для частичной даты document_date остаётся null, полный день возвращается ISO-датой. В evidence.id находится внутренний ключ строки БД; sources.id — локальный номер ссылки внутри анализа. Они не взаимозаменяемы.
validation возвращается как сохранённый JSON-объект; пустой объект старой записи не превращается в выдуманное passed=true. Confidence/impact и другие отсутствующие показатели не добавляются.

## Изоляция и ошибки

- 404 COMPANY_NOT_FOUND — компания отсутствует.
- 404 INSIGHT_NOT_FOUND — инсайт отсутствует, принадлежит другой компании или его запуск не COMPLETED. Эти случаи не раскрываются отдельно.
- 422 INVALID_CURSOR — некорректный курсор; для неверного limit/id используется стандартный ответ валидации FastAPI.
- 503 DATABASE_UNAVAILABLE — БД недоступна или не настроена; DSN и внутренние ошибки не возвращаются.

Запросы ленты, карточки и доказательств ограничены компанией и COMPLETED. Проверка принадлежности не заменяет будущую авторизацию пользователя. Пока авторизация не реализована, знание source_id само по себе не доказывает права пользователя на компанию.

## Проверки

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File backend/tests/run-profile-tests.ps1 -DatabaseRoot <checkout-PR-2>/database
```

Результат: **97 passed** (80 offline/API + 17 интеграционных), PostgreSQL 16.15, 6.86 секунды. Проверены изоляция компаний, точный текст доказательств, сохранение частичных дат, пустая история, отсутствующая компания/карточка, скрытие RUNNING/PENDING/FAILED, сортировка одинаковых дат, продолжение страниц после вставки нового инсайта, некорректные курсоры и ошибки БД. Чтению явно запрещён вызов AI. Прежние POST-тесты также проходят.
Проект: theyabliki-profile-6ff2a93371b1. Контейнер остановлен, том сохранён; синтетический baseline не изменился. Один известный warning Starlette про httpx TestClient. Реальных CSV, платных LLM-запросов, push, merge и PR не было.

Для больших историй владельцу БД стоит оценить составной индекс по (company_id, created_at, id) и планы запросов. В этом этапе индексы и миграции не изменялись. Пользовательские избранное/скрытие и история проверки прогнозов пока не входят в контракт.
