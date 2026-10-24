# Локальная подготовка агентного анализа — v1.21.0, первый срез

Следующий отдельный fake-only срез сохранения через существующие jobs описан в
[SYNTHETIC_JOB_EXECUTION.md](SYNTHETIC_JOB_EXECUTION.md). Сам read-only сервис
первого этапа остаётся неизменным и ничего не записывает.

Это фиксированный внутренний конвейер подготовки, не автономный LLM-агент.
Он доступен через `AnalysisPreparationService.prepare(source_id, news_id)` и
не подключён к HTTP, расписанию, RSS или paid execution. Сервис не принимает
SDK/analyzer и всегда использует встроенную локальную заглушку без сети.
Публичные API и production-конфигурация не меняются.

## Карта существующих компонентов

| Компонент | Ответственность и точка интеграции |
|---|---|
| `repositories/company_repository.py`, `news_repository.py` | Чтение существующих компании и новости |
| `services/company_context_service.py`, `repositories/company_context_repository.py` | Разрешённая проекция профиля, происхождение полей, структурные платёжные счётчики, неизвестные значения и ограничения интерпретации |
| `services/knowledge_base_service.py`, `search_service.py` | Локальный корпус и существующий TF-IDF поиск, до трёх фрагментов |
| `services/personalization_service.py` | Существующие инструкции компании и JSON-схемы; используется локальный `_local_rag` seam, внешний gateway не импортируется |
| `schemas/persisted_analysis.py`, `structured_analysis_service.py`, `validation_service.py` | Разбор ответа, проверка evidence/source metadata и существующие эвристики |
| `services/company_analysis_service.py`, `news_analysis_job_repository.py` | Владелец paid-path: атомарный claim, COMPLETED cache, RUNNING conflict, review/retry, ограничение попыток и fencing. Этот срез их не вызывает и не заменяет |
| `company_analysis_repository.py`, `evidence_repository.py`, `insight_service.py` | Атомарное сохранение анализов/evidence и чтение инсайтов; подготовка ничего сюда не пишет |
| `services/news_matching_service.py`, миграция 006 | Детерминированное сопоставление. Явно выбранная пара в подготовке не считается доказательством MATCHED |
| Миграции 001–006, исходная schema.sql | Существующие компании, новости, analyses/evidence, jobs/attempts, matching. Новая схема не требуется |

## Исполняемый план и журнал

План объявлен заранее в `services/analysis_preparation_service.py:PLAN` и
возвращается вместе с журналом в `schemas/analysis_preparation.py`.
Данные новости/компании не могут добавить инструмент, изменить порядок, создать
цикл, повтор, внешний вызов или запись в БД.

1. `load_snapshot`: существующие компания и новость; отсутствующие записи дают
   `COMPANY_NOT_FOUND` / `NEWS_NOT_FOUND`. Пустой или слишком длинный текст отклоняется.
2. `company_context`: существующий loader собирает facts/computed/missing/excluded.
   Оба чтения выполняются в одной короткой PostgreSQL-транзакции
   `REPEATABLE READ, READ ONLY`, затем соединение освобождается.
3. `rag_search`: поиск по точному исходному тексту через существующий search service;
   нет SQL-соединения во время поиска и локальной подготовки ответа. Пустой RAG
   даёт `INCOMPLETE / NO_RAG_CONTEXT` без вызова заглушки.
4. `prepare_input`: структурированные `news_from_db`, `company_source_assertions`,
   `analytical_source_assertions`, `model_assumptions=[]` и существующий question.
   Предел всего payload — 160000 байт UTF-8; предел контекста компании остаётся
   10000 байт. Данные не обрезаются: превышение завершает подготовку ошибкой.
5. `transfer_check`: вызывается неизменённый `external_transfer_guard`.
   `COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED` фиксируется как BLOCKED;
   внешний вызов невозможен. Продолжается исключительно локальная заглушка.
6. `local_stub`: фиксированный ответ `relevance=unknown` и пустые списки.
   Это проверка проводки данных, не модельный финансовый анализ или персонализация.
7. `self_check`: существующие parser/validator/PersistableAnalysis, точное соответствие
   пары/текста и evidence. JSON-schema valid не означает factual accuracy.

У каждого шага записаны инструмент, цель, необходимые данные, статус,
SHA-256 входа/результата и короткая сводка результата. Полные контекст и источники
доступны в prepared_input, точные фрагменты также в local_stub_result.evidence.
Хеши связывают журнал с содержимым, но не являются подписью или защитой от
намеренного редактирования отчёта. trace_id различается между запусками,
хеши одинаковых входов повторяемы. Статусы: OK/BLOCKED/FAILED/SKIPPED.
Исключения не печатаются: в журнал попадают только безопасные коды.

## Происхождение и самопроверка

- Сведения БД — утверждения импортированного источника, не независимо проверенные
  текущие факты. Контекст сохраняет origin и qualification, неизвестные год,
  валюту и единицы. Признак продукта не становится доказательством долга.
- Структурные платёжные количества остаются computed; суммы и контрагенты,
  исходный source_data и роли F–U не добавляются.
- RAG сохраняет точный текст, document/page/chunk_id/date/score. Отсутствующая
  дата остаётся null. Поиск не оценивает истинность и score не является confidence.
- model_assumptions отделены; заглушка их не создаёт. Реальная самопроверка выводов
  моделью пока `NOT_IMPLEMENTED`; factual_accuracy всегда `NOT_ASSESSED`.
- Противоречия источников, entailment цитат, актуальность OCR и обоснованность
  финансовых выводов требуют будущего этапа и экспертной проверки.

## Проверка на синтетических данных

Внутренний вызов из административного Python-кода с уже настроенной фабрикой
сессий **изолированной тестовой PostgreSQL**:

```python
from services.analysis_preparation_service import AnalysisPreparationService

synthetic_chunks = [{
    'source': 'synthetic-policy.txt', 'page': 1, 'chunk_id': 1,
    'text': 'Учебная аналитика: ключевая ставка влияет на кредитование.'
}]
service = AnalysisPreparationService(sessions, corpus_loader=lambda: synthetic_chunks)
report = await service.prepare('SYNTH-COMPANY-A', saved_synthetic_news_id)
assert report.status == 'PREPARED_LOCAL'
assert report.paid_calls == 0 and report.external_transfer_allowed is False
```

Unit-тесты: `python -m pytest backend/tests/test_analysis_preparation.py -q`.
PostgreSQL-тест использует существующие `identity_dsn` / `job_database`: отдельную
UUID-базу, актуальные миграции и синтетические данные. Проверяет конкурентные
подготовки, отдельные компании, отсутствие открытого соединения при RAG,
read-only rollback, сохранность news/jobs/insights/evidence и COMPLETED cache.
Реальный SDK в тестах заблокирован.

Проверка первого среза: **736 passed, 0 skipped** (backend + parser), включая
PostgreSQL integration и прежние проверки jobs/concurrency/context/evaluation.
Использован новый проект `theyabliki-orchestration-518a9e2e9d75`, отдельный том
`theyabliki-orchestration-518a9e2e9d75_audit_data` и существующая external network
`theyabliki-db-check-1a832d244c5f_default`. Локальный postgres:16 запускался по
подтверждённому ID образа, поскольку Docker не разрешал его тег. Внешние сокеты
были заблокированы с разрешением loopback; исходный fingerprint сохранён.
Контейнер проекта остановлен, сеть и том не удалялись. Реальных LLM-вызовов нет.

## Ограничения и следующий срез

Журнал пока возвращается в памяти и автоматически не сохраняется. Он содержит
закрытые исходные сведения: не печатать его в серверные логи, не прикладывать к
PR и не добавлять в Git. Для долговременного аудита нужен согласованный канал
приватного хранения и политика доступа/сроков; таблицы insights/evidence для
журнала не дублируются.

Не передавать local_stub_result в production persistence и не использовать этот
сервис как новый analyzer для CompanyAnalysisService. Подготовка не резервирует
paid job и не подтверждает право на платный вызов. Реальная генерация в будущем
должна оставаться внутри существующих claim/dispatch/fencing и атомарного commit
CompanyAnalysisService. Ни этот отчёт, ни успешная локальная проверка не обходят
COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED и не разрешают передачу DB-контекста.
Кэш paid результатов и попытки не изменены; повтор подготовки не создаёт записей.

Следующий отдельный этап: согласовать типизированный контракт preflight и
приватное хранение трассы в существующем job lifecycle, затем локальную проверку
обоснованности выводов; без реальных внешних вызовов и без автоматического retry.
