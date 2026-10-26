# Расширенная offline-коллекция saved-pilot — v1.29.0 (локально)

## Результат

3 синтетические компании, 9 настоящих сохранённых ответов DeepSeek: 1 исторический fixture без изменений и 8 новых полных результатов. Обрезанная первая попытка retail-inflation осталась только в ignored локальном аудите. Просмотр и seed не выполняют LLM-вызовов.

Запуск без .env: `docker compose -f compose.saved-pilot-demo.yml up --build -d --wait`. По умолчанию http://localhost:8082, synthetic-pilot-viewer / PulseDemo2026Viewer. Для локальной проверки без изменения старых окружений оставлено http://localhost:8088 (чистая БД); http://localhost:8089 — тест обновления отдельной копии v1.28.2. На тестовой машине использованы отдельные project, образы и свободные подсети. Override-файлы находятся только в ignored backend/data/collection_release_check; основной Compose и credentials не изменены.

## Совместимость и транзакционность

Миграций и изменений контракта API нет. Переиспользованы компании, grants, analyses, runs, evidence и JSON validation. Политики ACL и внешней передачи не ослаблены. Только offline seed подключает утверждённую коллекцию. Хеш pinned release, DTO/источники/исходные ответы/usage/reviewer проверяются до записи. Конфликты source_id/news identity и хешей вызывают отказ.

Чистое создание исторического пилота и восьми новых записей выполняется в общей транзакции под прежним advisory lock. При обновлении исходный исторический анализ/evidence/trace и посторонние записи не меняются. Записи коллекции имеют собственные digest, generation/import даты разделены. Исторический trace генерации сохраняется точно (VALIDATED); он не дополняется шагом импорта. Run имеет COMPLETED как состояние сохранённого результата.

## Проверки

- 73 профильных backend/unit/PostgreSQL теста PASS, 0 skipped: fake SDK, реальные сохранённые fixtures, 8 конкурентных импортов, чистый импорт и обновление, rollback при evidence/metadata, конфликт news identity, ACL/cache совместимость и повтор.
- 36 legacy/offline-readiness/config/auth тестов PASS (35 + один исправленный тест изоляции legacy CLI).
- 14 frontend тестов PASS: исторический и все восемь новых fixtures, исходные слова, источники, предупреждения, trace, fake/real различие. TypeScript PASS, Vite build PASS.
- Docker backend/frontend BUILD PASS из Git-контекста (tracked + согласованные untracked), без .env, ignored data, CSV/PDF и ключей. Cache только зависимостей.
- PostgreSQL/backend/frontend healthy, seed exit0 в чистой и upgrade-копии. 25 HTTP-проверок на каждой, 50 всего: login/me/3profiles/3feeds/9cards, совпадение raw-normalized полей/reviewer/trace, 401/403/logout204.
- Повтор seed на обоих томах: created0/unchanged8/new_llm_requests0.
- Upgrade: полный JSON исторического анализа и двух evidence до/после совпал; тестовая посторонняя компания сохранена.
- Browser http://localhost:8088: переключение металлургия/розница/производство, все3 на компанию, карточки и ссылки, trace и UNKNOWN/NEEDS_REVIEW; исторические16UNKNOWN/4NEEDS_REVIEW сохранены. Console errors/warnings:0.
- Frozen rules/holdout SHA-256 и исходные fixtures/ответы неизменны, secret scan PASS. Уже работавшие контейнеры: те же image/start timestamps. Новых LLM-запросов при интеграции:0.

## Ограничения

Финансовая достоверность всех результатов UNKNOWN. Источники — короткие исторические публичные фрагменты HTML→TXT, не банковские PDF, не текущие события и не позиция Альфа-Банка. Одна дата публикации неизвестна. Исходный текст модели не исправлен: формулировки о «одобренном» продукте, приоритетной отрасли и общие рекомендации сохранены с отдельными экспертными оговорками в UI; они не являются дополнительными findings reviewer. Наличие ссылки и JSON/provenance не доказывают смысловую поддержку. Экспертная проверка не заменяется эвристикой. Публичные credentials пригодны только для localhost-синтетики.

Сырые SDK-конверты (включая служебные reasoning-поля) и обрезанная попытка остаются только в локальном аудите, не включены в fixture/образ. Публикуются точный итоговый ответ, original request, нормализованный JSON, model/usage/cost без предположения валюты, finish_reason, даты, SHA, evidence и trace.

Коммит/push/merge не выполнялись. Рекомендуемый релиз v1.29.0.

## Файлы

- `README.md`
- `backend/.dockerignore`
- `backend/Dockerfile.saved-pilot`
- `backend/evaluation/pilot_collection.py`
- `backend/fixtures/pilot_collection_inputs_v1.json`
- `backend/fixtures/pilot_collection_preflight_v1.json`
- `backend/fixtures/saved_pilot_collection_v1.json`
- `backend/pilot_collection_demo.py`
- `backend/saved_pilot_demo.py`
- `backend/services/pilot_collection_input.py`
- `backend/services/pilot_collection_records.py`
- `backend/services/synthetic_draft_adapter.py`
- `backend/tests/test_auth_pilot_collection.py`
- `backend/tests/test_pilot_collection.py`
- `backend/tests/test_saved_pilot_demo.py`
- `docs/PILOT_COLLECTION_PREPARATION.md`
- `docs/SAVED_PILOT_COLLECTION.md`
- `docs/SUBMISSION_CHECK.md`
- `frontend/src/shared/api/mappers/pulseMappers.ts`
- `frontend/src/shared/constants/savedPilot.ts`
- `frontend/src/store/models/IPulse.ts`
- `frontend/src/widgets/Insight/InsightSections.tsx`
- `frontend/src/widgets/Insight/SavedPilotNotice.test.tsx`
- `frontend/src/widgets/Insight/SavedPilotNotice.tsx`
- `frontend/src/widgets/Layout/AlfaLayout.tsx`
