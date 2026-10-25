# Локальная оценка AI-процесса — v1.23.1

Дата: 25 октября 2026. Базовый HEAD: `ada481c5b60be222f1c9bf3b3a6b1464adad7f0a`.
Изменения v1.23.1 не закоммичены. Прежние документы, включая
`AI_QUALITY_EVALUATION_PLAN.md`, сохранены без изменений.

**Технический benchmark проходит; целевые пороги качества financial review не достигнуты.**
Реальная модель не проверялась. Внешних LLM-запросов — 0. Полнота содержательной
персонализации и обоснованность рекомендаций — **NOT_EVALUATED**.

## Реализация и методика

- `backend/evaluation/quality_fixtures.json`: 12 фиксированных сценариев, 24 утверждения,
  вымышленные профили/новость/аналитические тексты. У каждого утверждения заранее записаны
  label, категория и нормативное обоснование, отдельно от predictions и codes reviewer.
- `backend/evaluation/quality.py`: расчёт метрик, manifest, canonical comparison,
  проверка допустимого изменения draft. Прежний write_json/sanitizer используется повторно.
  CLI не имеет real-режима, DSN, произвольного пути входных данных или параметра модели.
- `backend/tests/test_auth_quality_integration.py`: реальный путь с сессией, ACL,
  прежними jobs, подготовкой, локальным RAG, fake SDK, reviewer и атомарной записью.
- `backend/tests/test_quality_unit.py`: агрегация метрик, воспроизводимость, structural
  source faults, контроль новых утверждений и изоляция CLI от settings/.env/SDK.
- `backend/schemas/preparation_diagnostics.py`, `backend/services/preparation_diagnostics.py`:
  строгая безопасная стадия/категория исключения. Используются только во внутреннем
  preparation report. Изменены `schemas/analysis_preparation.py` и
  `services/analysis_preparation_service.py`; публичные endpoints не менялись.
- `backend/tests/test_preparation_diagnostics.py` и дополнительная проверка в
  `test_analysis_preparation_integration.py`: fault injection и реальная READ ONLY ошибка БД.

Новая очередь, orchestration framework, миграция, retry policy и LLM-клиент не создавались.
`COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED` сохраняется. Изменений frontend нет.

Разметка независима **от предсказаний reviewer**: labels не вычисляются по его codes и
не менялись после измерения. Но автор разметки — автор реализации; внешняя независимая
экспертная проверка ещё PENDING. Поэтому это небольшой нормативный пилот, не золотой
банковский датасет и не оценка истинности финансовых тезисов.

## Результаты 12 сценариев

Каждый сценарий выполнен три раза в свежей UUID-базе с собственными синтетическими
учётными записями. Итого 36 fresh-run, отдельно проверено повторное обращение к той же
паре. У COMPLETED возвращается cache, у FAILED — CONFLICT без автоматического retry.
В Q02 дополнительно проверен независимый анализ той же новости другим пользователем
для компании B и запрет пользователю A читать этот кеш.

| ID | Содержание проверки | Решения planner | Итог задания | Результат benchmark |
|---|---|---|---|---|
| Q01 | Топливо, кредитный флаг=true | DRAFT → KEEP_WITH_WARNINGS | COMPLETED | PASS, профиль передан точно |
| Q02 | ПО, кредитный флаг=false, депозит=true; та же новость/RAG | DRAFT → KEEP_WITH_WARNINGS | COMPLETED | PASS, контекст другой, чужие сведения не примешаны |
| Q03 | Профиль топлива с изменением только кредитного флага | DRAFT → KEEP_WITH_WARNINGS | COMPLETED | PASS, контролируемое изменение входа |
| Q04 | Нет industry и okved_code | SEARCH_RAG → DRAFT → KEEP_WITH_WARNINGS | COMPLETED | PASS, один допоиск и пересмотр плана |
| Q05 | Во всём corpus один источник | SEARCH_RAG → DRAFT → KEEP_WITH_WARNINGS | COMPLETED | PASS, повтор не размножил evidence |
| Q06 | Нет источников | STOP | FAILED, NO_RAG_CONTEXT | PASS, draft не вызван, частичных результатов нет |
| Q07 | В risks[0] выдуманные условия кредита | DRAFT → REMOVE_CLAIM | COMPLETED | PASS, одно удаление, две полные проверки |
| Q08 | Те же условия только в summary | DRAFT → KEEP_WITH_WARNINGS | COMPLETED | PASS, предупреждения сохранены, summary не переписан |
| Q09 | Несуществующая ссылка 999 | DRAFT → STOP | FAILED, FINANCIAL_REVIEW_BLOCKED | PASS, нет insight/evidence/payload |
| Q10 | Существующая, но содержательно посторонняя ссылка | SEARCH_RAG → DRAFT → KEEP_WITH_WARNINGS | COMPLETED | PASS механики, поддержка тезиса осталась UNKNOWN |
| Q11 | Условная формулировка с неизвестными условиями договора | DRAFT → KEEP_WITH_WARNINGS | COMPLETED | PASS, не объявлена подтверждённой ошибкой |
| Q12 | Один пункт содержит оговорку и неподтверждённую цифру | DRAFT → REMOVE_CLAIM | COMPLETED | PASS механики, обнаружена потеря полезной оговорки |

В каждом fresh-run сверены allowlist/лимиты, отсутствие соединения БД во время fake SDK,
запрет внешней передачи, source metadata и точное происхождение текста, JSONB trace,
состояние jobs и отсутствие новых утверждений. До claim и после cache проверены чужая
membership и отсутствие news grant. Q02 проверяет также обратное направление доступа.
Синтетические уникальные маркеры региона B отсутствуют во входах A, и наоборот.

Для Q01/Q02/Q03 новость и corpus одинаковы, context fingerprints различаются.
Одинаковый намеренно пустой fake draft для Q01 и Q02 **не засчитан персонализацией**.
Контекст передан корректно — это проверяемая доставка данных, а не оценка полезности ответа.

Во всех 12 случаях canonical result совпал между тремя независимыми исполнениями:
анализ, evidence, findings, решения/наблюдения и счётчики. В canonical trace исключены
audit-хеши, которые могут включать технические DB timestamps/IDs; полные хеши сохранены
в raw_report. Company ID, текст, source IDs, даты, evidence и решения не исключались.
Context/news/corpus fingerprints также проверены на совпадение внутри каждого случая.
Стабильность при перестановке корпуса и равных retrieval scores здесь не утверждается.

## Метрики 24 финансовых утверждений

12 REQUIRE_REVIEW, 8 ACCEPTABLE_WITH_CAVEATS, 4 INDETERMINATE. В бинарные метрики
входят только первые 20. Положительный результат — адресный NEEDS_REVIEW-код ожидаемой
категории и поля; generic UNKNOWN и CITATION_ENTAILMENT_UNKNOWN не превращаются в TP.
На отрицательных примерах FP означает неподходящий предупреждающий диагноз, а не
«модель доказанно ошиблась в финансах». Несколько findings одного тезиса не размножают TP.

| Метрика | Результат |
|---|---:|
| TP | 9 |
| FP | 2 |
| FN | 3 |
| TN | 6 |
| Precision = 9/(9+2) | 81,82% |
| Recall = 9/12 | 75,00% |
| FPR = 2/8 | 25,00% |
| Утверждения со статусом NEEDS_REVIEW | 12 |
| Утверждения со статусом UNKNOWN | 12 |
| INDETERMINATE, исключены из confusion matrix | 4 |
| Financial correctness / semantic entailment | UNKNOWN / NOT_EVALUATED |

По отдельным findings, включая несколько на одном утверждении: 18 NEEDS_REVIEW,
21 UNKNOWN. Это другой знаменатель, его нельзя смешивать с числом утверждений.
Подтверждённых финансовых ложностей не установлено.

### Полный перечень утверждений

Полные тексты и обоснования находятся в quality_fixtures.json; таблица — краткое обозначение.

| ID | Gold label | Предмет | Review status | Классификация benchmark |
|---|---|---|---|---|
| P01 | REQUIRE_REVIEW | «Стоимость кредитования не меняется» | NEEDS_REVIEW | TP |
| P02 | REQUIRE_REVIEW | «Прямого изменения стоимости заёмного финансирования не произошло» | NEEDS_REVIEW | TP |
| P03 | REQUIRE_REVIEW | Неизвестные сумма, процент и срок договора | NEEDS_REVIEW | TP |
| P04 | REQUIRE_REVIEW | Макро-ставка 14% приписана кредиту компании | NEEDS_REVIEW | TP |
| P05 | REQUIRE_REVIEW | Кредитный продукт объявлен существующим кредитом | NEEDS_REVIEW | TP |
| P06 | REQUIRE_REVIEW | Отрасль объявлена доказательством экспорта | NEEDS_REVIEW | TP |
| P07 | REQUIRE_REVIEW | Число платежей объявлено оборотом | NEEDS_REVIEW | TP |
| P08 | REQUIRE_REVIEW | Число контрагентов объявлено прибылью | NEEDS_REVIEW | TP |
| P09 | REQUIRE_REVIEW | Гарантированная прибыль компании | NEEDS_REVIEW | TP |
| P10 | REQUIRE_REVIEW | Безусловный доход без слова «компания» | UNKNOWN | FN |
| P11 | REQUIRE_REVIEW | Нерелевантный источник якобы устанавливает условия займа | UNKNOWN | FN |
| P12 | REQUIRE_REVIEW | Источник якобы подтверждает график погашения | UNKNOWN | FN |
| N01 | ACCEPTABLE_WITH_CAVEATS | Если есть кредит; условия неизвестны | UNKNOWN | TN |
| N02 | ACCEPTABLE_WITH_CAVEATS | Гипотетическая фиксированная ставка | UNKNOWN | TN |
| N03 | ACCEPTABLE_WITH_CAVEATS | Возможно изменение спроса | UNKNOWN | TN |
| N04 | ACCEPTABLE_WITH_CAVEATS | Нельзя утверждать неизменность стоимости | UNKNOWN | TN |
| N05 | ACCEPTABLE_WITH_CAVEATS | Продукт не доказывает долг | UNKNOWN | TN |
| N06 | ACCEPTABLE_WITH_CAVEATS | Спорная фраза процитирована как некорректный пример | NEEDS_REVIEW | FP |
| N07 | ACCEPTABLE_WITH_CAVEATS | Макро-факт со ссылкой, без переноса на договор | UNKNOWN | TN |
| N08 | ACCEPTABLE_WITH_CAVEATS | Утверждение о различии факта и предположения | NEEDS_REVIEW | FP |
| U01 | INDETERMINATE | Условный расчёт без формулы и единиц | UNKNOWN | Исключён |
| U02 | INDETERMINATE | Неопределённое округление числа | UNKNOWN | Исключён |
| U03 | INDETERMINATE | Неоднозначное местоимение | UNKNOWN | Исключён |
| U04 | INDETERMINATE | Смешанная формулировка «по данным… возможно» | NEEDS_REVIEW | Исключён |

Пропуски P10/P11/P12 не скрыты: правила зависят от лексических шаблонов и не устанавливают
семантическую поддержку тезиса источником. Generic UNKNOWN честно сохраняет неопределённость,
но не выполняет требование обнаружить конкретный класс риска.

Ложные срабатывания N06/N08 показывают непонимание метаязыка: цитирование неверного примера
и описание различия факта/предположения ошибочно прочитаны как сами спорные утверждения.
Предупреждение само по себе не доказывает ложность тезиса и не даёт права автоматически
переписывать финансовые факты. Правила reviewer в этом срезе не изменялись для улучшения метрик.

Цели плана (минимум 11/12 обнаружений и максимум 1/8 FP) **не достигнуты**.
Зелёные pytest проверяют достоверность измерения и безопасность конвейера, а не прохождение
этих финансовых quality gates. На столь малом наборе нет статистической гарантии.

## Качество корректировки и источников

В Q07 и Q12 удалён ровно один заранее обозначенный пункт. Все прочие поля draft неизменны;
новых фактов/чисел/источников не появилось. После удаления повторились schema, exact
provenance и financial review. Дополнительный unit-test намеренно добавляет новый тезис
и проверяет, что correction checker обнаруживает нарушение.

Q12 показывает ограничение: удаление целого пункта удаляет и полезную оговорку в нём.
Это безопасная механическая стратегия, но не доказательство хорошего итогового анализа.
Summary Q08 остаётся с review-сигналами: автоматическая коррекция summary не разрешена.

Четыре структурных fault-теста отдельно проверяют несуществующий citation ID, дубликат
evidence ID, подмену текста и несовпадение document/page метаданных. Проверяются реальные
разные границы — reviewer, Pydantic и provenance. Старые PostgreSQL-тесты дополняют это
проверкой полного rollback при ошибке evidence/trace, blocker после корректировки и 8
конкурентами с одной попыткой. Никакого «источник существует → тезис подтверждён» нет.

## Диагностика PREPARATION_FAILED

Теперь при неожиданном Exception во внутреннем preparation report появляется optional
`diagnostic`: version, stage, family, historical_root_cause=UNKNOWN, retry_allowed=false.
Публичный error_code, статусы jobs и retry policy не меняются.

| Fault injection | Stage | Family | Результат |
|---|---|---|---|
| Ошибка repository | load_snapshot | RUNTIME | PREPARATION_FAILED, без повторов |
| Ошибка context loader | company_context | RUNTIME | PREPARATION_FAILED, без повторов |
| Ошибка corpus loader | rag_search | RUNTIME | PREPARATION_FAILED, без повторов |
| Некорректный тестовый тип лимита | prepare_input | TYPE | PREPARATION_FAILED, без повторов |
| Неожиданная ошибка guard | transfer_check | RUNTIME | PREPARATION_FAILED, guard не обходится |
| Ошибка фиксации stub result | local_stub | RUNTIME | PREPARATION_FAILED, без повторов |
| Ошибка после stub во время сборки | self_check | RUNTIME | PREPARATION_FAILED, без повторов |
| Реальная попытка записи в READ ONLY transaction | company_context | DATABASE | Запись отклонена, baseline не изменён |

Не вызываются str/repr(exception), чтение args/cause/locals/SQLSTATE или имени произвольного
класса. Stage и family — строгие allowlist. Secret-sentinel отсутствует и в report JSON,
и в stdout/stderr; отдельный hostile exception проверяет, что str/repr не вызываются.
Отдельно проверены категории VALUE, TYPE, CANCEL_OR_TIMEOUT для TimeoutError.

**Исторический неповторившийся PREPARATION_FAILED не объявляется исправленным.**
Показана локализация искусственных сбоев, а не установлена причина старого инцидента.
Диагностика остаётся в локальном отчёте/pytest-артефактах, долговременной таблицы нет.
CancelledError не перехватывается новым кодом: семантика отмены прежняя. Ошибка во внешней
по отношению к prepare части SyntheticNewsExecutionService (например, заморозка corpus)
не превращается автоматически в PREPARATION_FAILED и этим diagnostic не покрывается.

## Воспроизведение и артефакты

Только 24 утверждения, без PostgreSQL и без доступа к API-ключу:

```powershell
$env:PYTHON_DOTENV_DISABLED = '1'
$env:PYTHONPATH = (Resolve-Path backend).Path
& .\.venv-portability\Scripts\python.exe -B -m evaluation.quality
```

CLI сохраняет claims.json и manifest.json в уже игнорируемую Git директорию
`backend/evaluation-results/quality-<uuid>/`. Принимает только --help; --real и пути к
чужим данным отвергаются. Тест из отдельного интерпретатора блокирует dotenv и SDK
и подтверждает, что settings не импортировался. CLI не запускает 12 DB-сценариев.

Все сценарии и диагностические тесты:

```powershell
# PostgreSQL-переменные должны выставляться только проверенным isolation runner.
& .\.venv-portability\Scripts\python.exe -B -m pytest -q `
  backend/tests/test_quality_unit.py `
  backend/tests/test_preparation_diagnostics.py `
  backend/tests/test_auth_quality_integration.py
```

Без изолированного NEWS_IDENTITY_TEST_DATABASE_URL PostgreSQL-test будет skipped;
такой запуск нельзя выдавать за проверку всех 12 сценариев. В этой работе использован
прежний безопасный runner с проверкой Docker project/volume/override и baseline fingerprint.
Его профиль и полный прогон применяли только loopback UUID-дочерние базы и fake SDK.

Полный quality-report.json создаётся в tmp_path теста
`test_quality_twelve_scenarios_three_fresh_runs_and_isolation`. Он содержит manifest с
Git HEAD, версиями Python/зависимостей, source/fixture hashes, все три raw reports каждого
case, canonical results, context/news/corpus fingerprints и полные findings по 24 claims.
В отдельных tmp_path сохраняются 7 diagnostic.json. Эти файлы не добавлять в Git.
Исходные audit-хеши сохранены; конкретные пути последнего успешного запуска указаны
в итоговом отчёте задачи. Копия полного финального отчёта и семи диагностик сохранена в
`backend/evaluation-results/quality-v1.23.1-389f1dd4daa04df4a10d173b2322eefa/`.
Этот каталог проверен через git check-ignore и не входит в изменения Git.
Фактический smoke CLI создал отдельные claims/manifest в
`backend/evaluation-results/quality-ea23b915d3834538a03aeb2f7ceacf6d/`.

## Что исправлять перед подключением реального LLM

1. Проверить labels независимым экспертом; расширить небольшой набор контрпримеров,
   не подгоняя разметку под существующие правила.
2. Устранить P10/N06/N08 отдельным срезом обработки категоричности, цитат и метаязыка
   с защитой от удаления полезных формулировок. Не обещать семантическое доказательство regex.
3. Согласовать проверку конкретного тезиса против evidence и правила ручной эскалации:
   P11/P12 нельзя решить проверкой ID или совпадением слов. UNKNOWN не считать PASS.
4. Определить политику публикации summary с существенными findings и утраты содержания
   при Q12; существующий fake-процесс пока только сохраняет предупреждения.
5. Оценить содержательную персонализацию и рекомендации независимой rubric. Пока
   фиксированные fake-ответы не позволяют измерить эти свойства модели.
6. Продолжить диагностику старого PREPARATION_FAILED только по безопасным артефактам;
   не включать автоматические retry неопределённых попыток.
7. Сохранить внешний guard и требовать отдельное разрешение на любой реальный тест.
   Подключение модели не является частью этого среза и не разрешает передачу реальных данных.

## Проверки и Git

Промежуточный расширенный профиль: 105 passed (82,11 секунды), включая 36 fresh-run.
После добавления дополнительных unit-проверок выполнен полный безопасный прогон;
**908 passed, 0 skipped**, 226,05 секунды. Baseline fingerprint совпал до/после;
остановлен только project `theyabliki-orchestration-518a9e2e9d75`, том/сеть сохранены.
Команда локального CLI также завершилась успешно. `git diff --check` прошёл.
Коммит не создавался, push/merge/rebase не выполнялись. Миграции и frontend не изменены.

Предлагаемый коммит после просмотра:

```text
feat(eval): добавить воспроизводимую оценку локального AI-процесса

Синтетические сценарии, независимые от predictions labels и метрики reviewer,
проверки повторяемости, изоляции и безопасная диагностика подготовки без retry.

Версия: v1.23.1
```

В этот будущий коммит не включать пять прежних документов аудита/плана, реальные данные,
результаты evaluation и временные артефакты. Полный перечень нового кода приведён выше.
