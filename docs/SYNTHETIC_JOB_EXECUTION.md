# Синтетическое выполнение через существующие jobs — v1.21.1

Внутренний `SyntheticNewsExecutionService.analyze_saved(source_id, news_id)`
проверяет проводку подготовки → fake SDK → validation → persistence. Он не
зарегистрирован в FastAPI, не вызывается по расписанию и не является способом
включить внешнюю модель. Production endpoint, конфигурация, промпты и миграции
не меняются. Это дополнение к [read-only подготовке](ANALYSIS_ORCHESTRATION.md).

## Переиспользование вместо новой очереди

`CompanyAnalysisService.analyze_saved` остаётся владельцем всего жизненного цикла:

1. Читает существующие компанию/новость и атомарно делает claim существующего job.
2. Возвращает сохранённый COMPLETED без подготовки, контекста или fake SDK.
3. Для нового запуска завершает короткую транзакцию, отмечает dispatch и вызывает
   локальный адаптер через прежний `protected_ai.invoke` с прежним timeout.
4. Адаптер вызывает `AnalysisPreparationService`, проверяет соответствие исходного
   текста и контекста снимку claim, затем делает один вызов `LocalFakeAnalysisSDK`.
   Повторный вызов SDK в рамках одного адаптера явно запрещён.
5. Существующий `personalization_service` собирает question, разбирает JSON и
   применяет validation/PersistableAnalysis. Адаптер дополнительно сравнивает
   каждое evidence целиком с подготовленным источником: текст, дату, страницу,
   chunk_id, document, score и id. SDK источники не выбирает и не генерирует.
6. Прежний сервис проверяет владельца попытки (claim token / fencing), в одной
   транзакции сохраняет insight, все evidence, response_payload/insight_id попытки
   и COMPLETED в analysis_runs. Другие транзакции не видят частичный результат.

Новость повторно не создаётся. На одну пару остаётся один job; разные компании
имеют независимые jobs. RUNNING даёт существующий `ANALYSIS_ALREADY_RUNNING`.
При ошибке используется существующий FAILED + `retry_policy=REVIEW_REQUIRED`;
повтор возвращает существующий `ANALYSIS_RETRY_REQUIRED`, а не запускает SDK.
Правила административного retry, максимум две попытки, stalled/uncertain runs
и fencing не изменяются. Ошибка подтверждения статуса остаётся UNCERTAIN и не
приглашает к повтору. При потере ответа commit прежний сервис проверяет COMPLETED.

Подготовка повторно читает read-only snapshot после claim. Если текст или контекст
успели измениться, адаптер останавливается с `CLAIM_PREPARATION_SNAPSHOT_CHANGED`,
не смешивает разные версии входа и не вызывает fake SDK. Применяется прежняя
обработка ошибок jobs, без самостоятельного retry.

## Ограничение области записи

Fake-результат заполняет тот же кэш пары, что и настоящий анализ. Поэтому нельзя
использовать его на реальной компании, общей БД или frontend demo.

До обращения к БД сервис требует одновременно:

- явное `confirm_synthetic=True`;
- company source_id с префиксом `SYNTH-`;
- `postgresql+asyncpg` на loopback 127.0.0.1 / ::1;
- имя БД `test_news_identity_<32 hex>`, создаваемое существующим тестовым helper.

Обычная demo-БД, импортированная CSV-БД и общий сервер отклоняются до claim.
Это предохранитель тестового инструмента, не универсальное доказательство
синтетичности произвольной БД с похожим именем: оператор должен использовать
только отдельные UUID-базы существующей тестовой инфраструктуры.

Сервис принимает только встроенный тип `LocalFakeAnalysisSDK`. У него нет HTTP,
API-ключа, provider URL, retry, fallback или выбора модели. Test double ошибки
подставляется только в тестах. Ограниченный prepared_input передаётся копией.
Результат помечается `model_name=local-fake-orchestration-v1`,
`prompt_version=local-orchestration-v1`, `relevance=unknown`.
Он не придумывает финансовых фактов и возвращает пустые списки выводов.

`validation.passed` у сохраняемого fake-результата всегда false, добавляются
`SYNTHETIC_FAKE_ANALYSIS_NOT_FOR_DECISIONS` и `FACTUAL_ACCURACY_NOT_ASSESSED`.
Пустые финансовые предупреждения, корректный JSON и точная копия evidence не
подтверждают истинность вывода. Реальная персонализация и модельная самопроверка
по-прежнему не реализованы этим fake-срезом.

`COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED` сохраняется в preparation trace.
После него разрешён только локальный fake; внешний analyzer не подключается.
Прежний default analyzer на свежей паре продолжает блокировать DB-контекст.

## Отчёт и будущее долговременное хранение

Возвращается `SyntheticExecution`: status, run_id, стандартный сохранённый response,
preparation report и пять execution steps с хешами, статусами и сводками:
claim, preparation, fake_llm, validate_result, persist. Все счётчики и trace
хранятся отдельно для каждого вызова, без общего изменяемого журнала.
При REUSED подготовка/SDK пропущены. При конфликте или ошибке отчёт содержит
безопасный код, а не исходное исключение, DSN, заголовки или содержимое ключа.
CancelledError не превращается в успех; существующий сервис выполняет обработку
статуса, а отменённый вызывающий код может не получить журнал из памяти.

Журнал пока не долговечен: падение процесса может его потерять, но состояние job
остаётся в PostgreSQL. Для следующего этапа предлагается приватный audit artifact
с ключом `(run_id, attempt_no, trace_id, version)` и SHA-256, с ACL/сроком хранения
и атомарной публикацией. Для транзакционной ссылки на artifact/status понадобится
отдельное согласование расширения существующего job lifecycle (либо outbox), а
не новая очередь анализа или копии таблиц insights/evidence. Журнал preparation
не следует помещать в публичный response_payload или логи: он содержит контекст.

## Проверка и использование

Только внутри синтетической UUID-базы с применёнными миграциями и тестовыми
компанией/новостью:

```python
from services.synthetic_news_execution_service import SyntheticNewsExecutionService

executor = SyntheticNewsExecutionService(
    sessions, corpus_loader=lambda: synthetic_chunks, confirm_synthetic=True,
)
report = await executor.analyze_saved('SYNTH-COMPANY-A', saved_synthetic_news_id)
assert report.status == 'COMPLETED'
assert report.fake_calls == 1 and report.paid_calls == 0
cached = await executor.analyze_saved('SYNTH-COMPANY-A', saved_synthetic_news_id)
assert cached.status == 'REUSED' and cached.fake_calls == 0
```

Профильные тесты: `test_synthetic_execution_unit.py` и
`test_synthetic_execution_integration.py`, вместе с существующими preparation/jobs
тестами. PostgreSQL-набор проверяет независимые соединения и восемь одновременных
запусков; ошибку fake SDK; невалидный JSON; подмену текста evidence; ошибку второй
записи evidence с откатом первой и insight; COMPLETED cache; разные компании;
отсутствующие записи; изменение контекста после claim; прежний внешний guard.
Ни тесты, ни инструмент не вызывают реальные модели или RSS.

Полная безопасная проверка второго среза: **751 passed, 0 skipped** (backend и
parser), включая PostgreSQL integration. Использован только наш изолированный
проект `theyabliki-orchestration-518a9e2e9d75` с отдельным томом и прежней external
network `theyabliki-db-check-1a832d244c5f_default`. Внешние сокеты заблокированы,
loopback разрешён, SDK подставной. Исходный fingerprint сохранён; свой контейнер
после тестов остановлен, сеть и том не удалены. Production Docker smoke отдельно
не повторялся: образ, API и production-конфигурация не менялись.
