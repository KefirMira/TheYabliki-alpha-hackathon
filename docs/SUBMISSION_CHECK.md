# Проверка сдаваемого окружения — 26 октября 2026

HEAD исходников: 9082be42f44b612ef5478a513c9a3f558af451c5, integration/frontend-backend.
Подготовка сдачи v1.27.1. Новых функций AI и платных вызовов нет.

## Статус

**Чистая холодная Docker-сборка пока НЕ подтверждена.** Первая backend-сборка
остановилась на PyPI ReadTimeout при загрузке scikit-learn. После этого в
Dockerfile добавлены timeout загрузки 120 секунд и BuildKit pip cache.
Повторная backend-сборка и загрузка node/nginx шли со скоростью десятки KB/s;
они остановлены без удаления кэша и данных. Для полного подтверждения сдачи
нужно завершить команду clean launch из README на доступной сети, затем проверить
тот же сценарий через nginx. Успешный прежний live smoke не заменяет эту проверку.

## Что проверено сейчас

- 31 targeted pytest: packaging (5), Docker-контракты и dataset policy (26).
- Оба синтетических профиля: строгий CSV audit, совпадение file/row hashes с release,
  построение DTO и fake draft без внешнего SDK.
- TypeScript и production frontend build: успешно на локальном Node.js.
- Установленные Python зависимости: pip check без нарушений; npm ls без ошибок.
- Собрана отдельная runtime smoke-image из текущих исходников и уже установленного
  ранее проверенного слоя зависимостей. Это НЕ холодная submission image и НЕ
  опубликованная зависимость для команды жюри.
- Docker project pulse-submission-check-20261026, отдельный новый том и
  test_submission_demo; marker pulse:isolated-company-import:v1.
- Все SQL schema/migrations 002–007 применены; 22 public таблицы, /ready=200.
- 20 реальных HTTP проверок **напрямую backend**: health, ready, docs, OpenAPI
  с конкретными auth/profile/capabilities/dataset routes; 401 без сессии и при
  неверном пароле; login/me; две компании и 403 чужой; профиль/capabilities/feed;
  создание синтетической новости; fake analysis 201 COMPLETED; карточка с одним
  TXT evidence, financial_review и orchestration; повтор 200 с тем же insight;
  feed; logout 204 и отзыв сессии 401.
- Повтор seed: 2 компании, 1 аккаунт, 2 memberships; прежний job/analysis/evidence
  (по одному) и их контрольные отпечатки неизменны. Restart backend/PG, ready=200.
- Секреты по проверенным credential patterns не обнаружены. В tracked Git нет
  CSV/PDF/SQLite/.env. Это техническая проверка шаблонов, не абсолютное доказательство.
- 7 frozen raw SHA-256 и 46 защищённых прежних документов/артефактов неизменны.
- git diff --check без ошибок. Шесть прежних EOL-only статусов сохранены, не входят
  в предлагаемый состав изменений.
- Полная регрессия и новые LLM-запросы не запускались.

## Что ещё НЕ подтверждено

- Завершение холодной сборки обоих image из Docker Hub/PyPI/npm.
- Same-origin nginx HTTP/browser smoke именно нового submission Compose.
  Локальный frontend build и ранее проверенная интеграция не считаются заменой.
- Тариф/квота организаторов и централизованный денежный лимит: в fake demo не нужны.
- Финансовая достоверность ответов: JSON/provenance и reviewer её не доказывают.
- Полный CVE/security или юридический аудит зависимостей не выполнялся.

## Локальная особенность Docker

Стандартные address pools исчерпаны другими сохранёнными сетями. Ничего не удалено.
Для собственного smoke создана отдельная сеть 172.16.250.0/24 после проверки
существующих подсетей и маршрутов. У другого пользователя подсеть может быть занята:
выбирать её автоматически нельзя. Необязательный compose.submission.network.yml
принимает явно проверенный SUBMISSION_SUBNET. Default Compose не задаёт подсеть.

## Повтор проверки

Команды чистого запуска, локальный .env, аккаунт, адреса и остановка — в README.
После успешной сборки проверить сценарий docs/JURY_DEMO.md, затем:

~~~powershell
docker compose -f compose.submission.yml exec backend pip check
docker compose -f compose.submission.yml run --rm seed
docker compose -f compose.submission.yml stop
docker compose -f compose.submission.yml up -d --wait
~~~

При использовании network override добавлять его ко всем этим командам.
Не удалять том; seed не является средством смены пароля.

## Зависимости

35 закреплённых web Python пакетов, 540 npm inventory entries из lock,
304 различных upstream LICENSE/NOTICE блока в THIRD_PARTY_NOTICES.md.
Необязательный OCR stack не входит в submission runtime; PyMuPDF отдельно
отмечен как AGPL/commercial. Лицензия на собственный код не назначалась.

## Неизменные ограничения

Default fake не читает ключ из .env, не вызывает провайдера. Organizer включается
только отдельным override и подтверждением конкретной новой пары; сейчас не запускался.
Глобальный COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED, ACL, jobs и retry policy
не изменены. Реальные CSV/PDF/платежи, локальные пароли и пилотные private artifacts
не копируются в Git или Docker context.

## Подготовленные файлы (20)

- README.md
- .env.example
- THIRD_PARTY_NOTICES.md
- compose.submission.yml
- compose.submission.organizer.yml
- compose.submission.network.yml
- docker/submission-marker.sql
- backend/.dockerignore
- backend/Dockerfile.submission
- backend/requirements-runtime.txt
- backend/submission_demo.py
- backend/fixtures/submission_profiles.json
- backend/fixtures/submission_release.json
- backend/fixtures/submission_rag/synthetic-rate.json
- backend/tests/test_submission_packaging.py
- frontend/.dockerignore
- frontend/Dockerfile
- frontend/nginx.conf
- docs/JURY_DEMO.md
- docs/SUBMISSION_CHECK.md

Проверочное окружение остановлено. Собственные том/сеть сохранены.
Временные smoke runners, пароли и HTTP-отчёты остаются только в игнорируемом
backend/data/submission_check и в предлагаемый коммит не входят.

Локальный коммит подготовки сдачи согласован отдельно при сохранении
неподтверждённого статуса cold build и nginx E2E:
chore(submission): подготовить воспроизводимый запуск для жюри

Версия: v1.27.1

## Ограниченный повтор холодной сборки

Существующий download cache использован. Выполнено по одному Compose build для
backend и frontend параллельно, с жёстким пределом 240 секунд на каждый процесс.
Оба остановлены по этому пределу (240.22 s, exit 124). Backend использовал
закэшированные wheels, но не завершил скачивание NumPy 16.7 MB с PyPI;
frontend не завершил загрузку слоя node:22-alpine размером 56.22 MB из registry.
Новых повторов не запускалось. Это блокер загрузки зависимостей, а не полученная
ошибка компиляции приложения. Нельзя объявить итоговую сборку успешной.

- BUILD: FAIL — превышено ограниченное время загрузки.
- nginx E2E: BLOCKED / не выполнен, готовых submission images нет.
- Backend/frontend health нового clean Compose: не проверены из-за сборки.
- Fresh PostgreSQL: PASS — healthy, marker корректен, 22 public таблицы,
  companies=0 до seed, schema/migrations успешно применены.
- Проверена Compose config: fake/demo, пустой API-ключ, четыре сервиса.
  В runtime/build нет обязательной зависимости от local ignored-файлов,
  кроме локального .env, созданного по документированным полям.
- Создан отдельный project pulse-submission-clean-20261026 с собственным томом
  и проверенной подсетью 172.16.251.0/24 (network override).
  Проверочные контейнеры остановлены, том и сеть сохранены. Чужие ресурсы не изменены.
- Предыдущие 20 direct-backend HTTP проверок не засчитываются как nginx E2E.

Минимальный путь при такой сети — успешно собрать и проверить эти же образы
на машине с доступом к PyPI/Docker Hub/npm, передать docker save archive
с проверяемым SHA-256 и использовать docker load + compose up --no-build --pull never.
Команды добавлены в README; архив сейчас не создан, его проверка не заявляется.

В этом повторе изменены только README.md и данный отчёт. Код, Dockerfiles,
политики LLM и frozen fixtures не изменялись. Локальный .env и build-логи
исключены из Git. Новых LLM-вызовов, полной регрессии и Git-коммитов не было.

## Финализация v1.27.1

Основной Compose запуск и резервная передача предварительно проверенных образов
описаны в README. Полностью без-Docker запуск не проверен и как готовый вариант
не заявляется. Сетевые блокеры cold build/nginx E2E остаются открытыми.
При финализации сборка, LLM-вызовы и полная регрессия не повторялись.
Шесть прежних EOL-only файлов не включаются в коммит; frozen bytes сохраняются.
