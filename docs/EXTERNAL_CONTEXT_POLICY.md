# v1.26.0: локальная подготовка внешнего контекста

Статус: только LOCAL_PREVIEW_ONLY, 0 внешних запросов. Новый код не подключён
к FastAPI, SDK, jobs или сохранению результатов. Реестр разрешений по умолчанию
пуст. Это проверяемый первый срез контроля передачи, а не включение реального AI.

## Реальные поля и классификация

Источник классификации: database/schema.sql, миграции 002–007,
backend/repositories/analysis_tables.py, company_context_repository.py,
company_context_service.py. Наличие в PostgreSQL НЕ означает публичность.

| Объект/поля | Категория | Политика этого среза |
|---|---|---|
| companies.id/source_id/name/inn/ogrn/website | Идентифицирующие, потенциально публичные только после отдельной проверки | Всегда исключены |
| industry, region | Контекст бизнеса; происхождение/права из БД не установлены | Только точное отдельное разрешение; сейчас ни одного |
| revenue/revenue_year | Внутренние финансовые; валюта/единицы могут быть неизвестны | Запрет |
| employee_count/client_status | Внутренние кадровые/клиентские | Запрет |
| source_data, CSV attributes, file hashes/line provenance | Смешанные, неизвестные и внутренние | Запрет |
| MAINOKVED, диапазоны численности | Импортированные утверждения, не доказательство публичности | Не входят в DTO |
| product flags, factoring, FTS_FLAG | Внутренние банковские/операционные | Запрет |
| company_payments: amount/count/currency/date/period/type/description/source_data, идентификаторы сторон | Платёжные, финансовые, идентифицирующие | Запрет включая агрегаты количества и контрагентов |
| persons, company_person_links, внешние F–U связи/роли | Идентифицирующие; семантика F неизвестна | Запрет |
| news_articles: title/content/url/source_name/source_id, dates/language/hash/input_kind | Текст/метаданные источника; приватный пользовательский ввод возможен | Только content с news ACL и отдельным точным разрешением; остальные исключены |
| RAG text/document/page/chunk/date/publisher | Источник/документ; локальность, PDF и банковская атрибуция не дают права передачи | Каждый текст отдельно; builder пока не выбирает корпус |
| runs/jobs/attempts/cache payload/insights/validation/evidence | Внутренние результаты и тексты, потенциально содержат исходные данные | Не являются источником DTO |
| auth users/password hashes/sessions/token hashes/memberships/grants | Секреты и внутренние права | Только локальная проверка, никогда DTO/audit |

## Аудит существующих путей

- company_analysis_service._profile_for_analysis -> load_company_context:
  industry/region/revenue/status и CSV-признаки плюс payment_structure.
  default_analyzer и _profile_for_analysis вызывают external_transfer_guard.
- personalization_service._analyze_for_company формирует question из контекста
  либо CompanyProfile и текста новости. Без локального RAG guard вызывается до этого.
  Внутренняя инъекция local_rag — доверенный тестовый контракт, не публичное разрешение.
- rag_service.analyze_with_rag вставляет найденные локальные фрагменты и имена
  документов в messages -> chat.completions.create. Его debug print выводит model,
  finish_reason, usage. Это legacy SDK-модуль, не новый policy-path.
- analysis_gateway лениво вызывает personalization/RAG. Legacy endpoints защищены
  существующим legacy_denied; новые ACL/guard не изменялись.
- synthetic_gateway_input + synthetic_draft_adapter используют pinned fixture DTO
  с verify_input до SDK; это отдельное разрешение синтетического пилота, не разрешение БД.
- analysis_preparation_service возвращает evidence.text и bundle, а также tool log:
  это внутренний содержательный trace, его нельзя автоматически экспортировать.
- company_analysis_service сохраняет payload cache и insight/evidence в транзакции;
  synthetic_gateway_execution_service сохраняет orchestration. Эти данные приватны
  и остаются под ACL; success JSON/provenance не доказывает финансовую достоверность.
- document_service/knowledge_base_service/pdf_service печатают имена/пути/статистику;
  evaluation/runner и локальные pilot tools сохраняют содержательные артефакты.
  Они не являются безопасным audit sink. Новый путь их не вызывает.
- Новый модуль не импортирует SDK/HTTP, dotenv, файловый writer или logging.
  Содержимое запрещённого контекста и исключений не копируется в audit.

Это статический аудит найденных прикладных путей, а не доказательство отсутствия
утечек во внешних middleware, APM, SQL echo, shell history или будущих изменениях.
Их конфигурация требует отдельного эксплуатационного контроля.

## Поток и компоненты

Действующий token hash
 -> CompanyContextBuilder
 -> auth principal (срок/отзыв/active), can_analyze membership, news grant
 -> существующие company/news/context repositories
 -> внутренний InternalContext (только industry/region/news; RAG пуст)
 -> ExternalContextPolicy
 -> SafeExternalContextDTO
 -> повторная проверка выдачи и целостности DTO
 -> LLMAnalysisService.preview
 -> строго встроенный FakeLLMTransport
 -> NOT_EVALUATED, financial_truth UNKNOWN; внешних запросов 0.

DB connection закрывается до policy/transport. Ошибка ACL — 401/403 без чужих данных.
InternalContext скрывает repr; значения полей DTO исключены из repr.
Builder пока переиспользует существующий load_company_context: его внутренние
агрегаты читаются, но НЕ попадают в InternalContext. Отдельную оптимизацию projection
можно сделать позже; новый набор SQL/дублирование правил не добавлены.

## Политика

Deny by default, обязательны industry и region; отсутствие любого — отказ.
Никакие DB-флаги synthetic/public, HTTP-флаги или caller dictionaries не разрешают передачу.
Разрешение Release создаётся только доверенным локальным операторским кодом:
scope SHA-256 source_id, конкретное поле, SHA-256 точных UTF-8 bytes,
REVIEWED_PUBLIC либо APPROVED_SYNTHETIC, organizer/news-analysis,
timezone-aware expires, review_ref. Это не юридическое доказательство согласия.
Сейчас нет loader/CLI/endpoint выдачи Release; штатная конфигурация пустая.
Для тестов разрешения созданы исключительно для выдуманных строк.
Неизвестный provenance, истечение, другая компания/цель/провайдер,
изменённый news/RAG, лишнее поле или ошибка политики дают общий отказ.

DTO extra=forbid/strict/frozen: industry<=320, region<=128, news<=4000,
до трёх RAG-текстов по <=4000 символов. Других полей нет; ORM/SQL result/dict не принимаются.
Policy выдаёт конкретный экземпляр и держит его digest; перед transport проверяются
identity, hash и повторная schema validation. model_copy и подмена полей отклоняются.
Python in-process код остаётся доверенным: это не sandbox против злонамеренного
кода с доступом к private атрибутам. Реестр выдач и audit живут в памяти и должны
иметь request scope; не использовать policy как бесконечный singleton.

## Prompt injection и пределы этого этапа

Текст не интерпретируется как инструкция: fake transport не строит prompt и не
исполняет инструменты, URL или код из текста. SYSTEM задаёт будущую границу
«данные, не инструкции», но не используется как доказательство защиты реальной LLM.
Просто кавычки/JSON или совпадение SHA не устраняют prompt injection.
Перед реальной интеграцией нужны точный message renderer с разделением system/data,
ограниченный allowlist инструментов существующего adaptive controller,
adversarial-тесты, запрет сетевых tool calls и повторная проверка output.
В этом срезе нет произвольного transport callback и параметра real=true.
Тип policy и transport проверяется при создании сервиса и непосредственно перед
preview; замена transport после создания отклоняется. Вызывается фиксированный
метод встроенного fake-класса, а не переопределённый callback экземпляра.

## Audit и сохранение

Audit содержит только stage/decision/code. Нет текстов, SQL IDs, scope hashes,
паролей, token hashes или сырых исключений. При отказе — общий PolicyDenied.
Audit не записывается в jobs/insights: fake preview не создаёт COMPLETED.
JSON/provenance/reviewer/atomicity прежнего анализа сохраняются без изменений;
новый NOT_EVALUATED не является сгенерированным анализом.
До подключения SDK потребуется атомарное присоединение audit к существующему
validation.orchestration внутри прежней транзакции; отдельной очереди/таблиц нет.

## Какие данные потенциально смогут покинуть backend

Только после отдельного согласования реального transport и операционных разрешений:
два отдельно разрешённых описания industry/region, отдельно разрешённый текст
новости и до трёх отдельно разрешённых RAG-фрагментов. Даже такая комбинация
может косвенно идентифицировать компанию — требуется оценка совокупности.
Названия, ИНН/ОГРН, IDs, платежи и их агрегаты, банковские признаки, доходы,
произвольный source_data/ORM, auth и прежние traces исключены.
СЕЙЧАС не покидает ничего: реального transport/endpoint/разрешений нет.
Проверка совокупного раскрытия НЕ реализована. Разрешения отдельных полей
разрешают только локальный preview, никогда не передачу их комбинации.
Внешняя передача остаётся заблокированной независимо от этих разрешений.

## До следующего этапа

Нужны доверенный проверяемый реестр/отзыв разрешений с юридическим основанием,
проверка совокупной идентифицируемости и DLP, corpus-level и per-fragment review,
повторная live ACL/policy проверка непосредственно перед реальным send,
централизованные лимиты/учёт расходов и уже существующий job claim.
Timeout/unknown outcome нельзя превращать в автоматический retry.
Сохранить COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED до отдельного решения;
этот DTO сам по себе не является разрешением обходить guard.


## Проверки и состав v1.26.0

Финальный профильный прогон: 109 passed, 0 skipped, 41,96 с.
Новые unit-тесты: запреты полей, неизвестные права/происхождение, каждый
news/RAG release отдельно, истечение/другая цель/provider/scope, extra fields,
model_copy/подмена DTO, фиксированный fake transport, один preview,
размеры/дубликаты/отсутствующие поля, ошибки без содержимого в audit,
синтетический injection без исполнения и ACL до чтения.
Новый PostgreSQL integration: существующий синтетический actor/session,
company/news ACL, default policy denial, чужая компания, отзыв сессии,
отсутствие созданных attempts.
Регрессия: прежний guard/context, frozen holdout, preparation, adaptive
atomicity/cache и synthetic gateway tests.
Полная регрессия всех backend/frontend тестов на этом этапе не запускалась;
frontend, API contracts, Docker configuration и миграции не изменены.
git diff --check и отдельная whitespace-проверка четырёх новых файлов пройдены.
Существующие frozen SHA-256 неизменны; 46 исходных документов/артефактов
проверены по сохранённым хешам. Новые файлы не содержат локальных private значений.
Шесть прежних EOL-only статусов сохранены без новых изменений.

Новые файлы:
- backend/services/external_context_policy.py
- backend/tests/test_external_context_policy.py
- backend/tests/test_auth_external_context_integration.py
- docs/EXTERNAL_CONTEXT_POLICY.md

Сообщение согласованного локального коммита:
feat(policy): подготовить локальный контроль передачи контекста компании

Live ACL, deny-by-default разрешения, строгий DTO и fake-only preview
без изменения guard и без внешних запросов.

Версия: v1.26.0
