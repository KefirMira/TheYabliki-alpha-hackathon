# Интеграция frontend ↔ backend

Проверено 25.10.2026 в отдельном managed worktree:
C:/Users/nasty/.codex/worktrees/frontend-backend-integration/TheYabliki-alpha-hackathon

Ветка integration/frontend-backend, исходный HEAD f4ca5b558a53522ea97fa64f46cad2d907c28e42.
Frontend взят из origin/feature/frontend-mvp, HEAD 07e5bb31236cea61633474dbdd93b671207ebc64.
Только каталог frontend перенесён из снимка ветки; Git merge/rebase не выполнялись.
До фиксации v1.25.0 frontend целиком новый относительно backend HEAD и отображался как ?? frontend/.
Ниже сохранён отчёт первоначальной интеграции; результаты повторной проверки и полный состав
коммита v1.25.0 приведены в последнем разделе. Публикация не выполнялась.

## Выполненный срез

Реальная цепочка: форма с паролем → POST /api/auth/login → индивидуальный Bearer →
GET /api/me → серверные memberships → профиль → лента → карточка → POST logout.
Возврат 204 обрабатывается без JSON.parse. После logout токен недействителен,
защищённые страницы снова требуют вход. Неверный пароль не включает локальный demo-login.

Токен хранится только в sessionStorage вкладки; он не попадает в Redux, URL, VITE_* или отчёт.
На refresh вызывается /api/me. Ошибка проверки закрывает локальную сессию.
Профиль, лента и анализ сбрасываются при смене актёра; старые ответы отбрасываются
по поколению сессии. Глобальный cache профилей удалён. Смена компании из карточки
переходит на ленту выбранной компании. Серверные ACL остаются обязательными.

Наличие llm_config не открывает анализ: проверяются company capabilities;
UNKNOWN, ошибка и BLOCKED запрещают основной submit. Demo seed даёт только чтение.
UI не является защитой API: права, jobs и guard проверяет неизменённый backend.

Backend FastAPI, миграции, production-prompts, DTO и guard не изменены:
достаточно существующей v1.24.1 и её защищённого integration_demo.
Новый API или обход ACL не добавлялся.

## Происхождение данных и честность интерфейса

- TXT и PDF сами по себе не доказывают банковское авторство.
- Блок банковской позиции выводится только при совпадении document/page/chunk
  и сохранённой provenance с attribution_status=VERIFIED и publisher=Альфа-Банк.
  Синтетический источник не выдаётся за банковскую позицию.
- Профиль API не сообщает издателя/валюту: UI показывает нейтральный источник,
  Decimal-строку без потери точности и неизвестные единицы/валюту.
- validation.passed означает технический результат, не финансовую достоверность.
- Структурированный financial_review показывается отдельно: UNKNOWN,
  NEEDS_REVIEW и CONFIRMED_ERROR не смешиваются.
- Синтетические seed-инсайты помечаются учебными. Если review отсутствует,
  это явно написано; выдуманные counts и показатели уверенности не создаются.
- Банковская витрина остатков/операций явно обозначена вымышленной.
- Правая панель — сведения сохранённой записи, не доказательство реально
  исполненного автономного агентного цикла.

## Изолированный запуск, использованный при проверке

Docker project: pulse-integration-app-20261025.
Новый том: pulse-integration-app-20261025_integration_pgdata.
БД: test_integration_demo с маркером pulse:isolated-integration-demo:v1.
PostgreSQL не публикует host-порт. Применены schema.sql и миграции 002–007.
При ограничениях Docker использована существующая тестовая external network;
backend направлен на уникальное имя собственного PostgreSQL-контейнера,
чтобы общий alias postgres не выбрал другую БД. Чужие контейнеры не изменялись.

- Frontend: http://127.0.0.1:5173
- Backend: http://127.0.0.1:58145
- Swagger: http://127.0.0.1:58145/docs
- Swagger через dev proxy: http://127.0.0.1:5173/docs

AI_MODE=demo; все LLM-переменные в контейнере пусты; RSS не запускался.
Свежий Docker-слой исходников собран offline поверх проверенного dependency image
pulse-synthetic-gateway-v1240-check:20261025.
Чистая переустановка Python-зависимостей из registry в этой проверке не подтверждена.

Два синтетических пользователя:
synthetic-demo-a → DEMO-001 (2 инсайта), DEMO-003 (пусто);
synthetic-demo-b → DEMO-002 (1 инсайт).
Пароли случайные локальные, в отчёт не включены.
В этой проверке их локальный файл: backend/data/integration_app/credentials.private.json.
Весь backend/data исключён из Git; не передавать его frontend-команде или в архив исходников.
Открывать пароль только локально для входа, не публиковать содержимое файла.

Seed: CREATED → UNCHANGED → после HTTP/login/logout снова UNCHANGED.
В БД: 3 компании, 2 пользователя, 3 memberships, 3 grants,
3 инсайта, 3 evidence, 0 news jobs, 0 attempts.

## Воспроизведение в новом окружении

Подробный backend seed: [INTEGRATION_DEMO.md](INTEGRATION_DEMO.md).
Из корня интеграционного worktree, Docker Desktop Linux containers, Compose v2:

~~~powershell
$env:INTEGRATION_DEMO_DB_PASSWORD = [guid]::NewGuid().ToString('N')
$env:INTEGRATION_DEMO_PORT = '8000'
docker compose -p pulse-integration-review -f compose.integration-demo.yml build backend
docker compose -p pulse-integration-review -f compose.integration-demo.yml up -d --wait postgres backend
docker compose -p pulse-integration-review -f compose.integration-demo.yml run --rm seed
docker compose -p pulse-integration-review -f compose.integration-demo.yml run --rm seed python -B -m integration_demo --expected-database test_integration_demo --apply --confirm-isolated
~~~

Последняя команда интерактивно запросит два независимых пароля. Повторный seed
требует тех же паролей; существующий пароль PostgreSQL нельзя генерировать заново
для существующего тома. Не использовать эту последовательность против общей БД.
Для Docker-хоста с ограниченными сетями нужен проверенный override; не выбирать
чужую сеть или БД автоматически и не выполнять prune.

Frontend, Node.js 24/npm 11:

~~~powershell
$env:VITE_BASE_API = ''
$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:8000'
npm --prefix frontend ci
npm --prefix frontend run dev
~~~

Пустой BASE использует same-origin dev proxy, сервер слушает только loopback.
Production dist требует отдельного reverse proxy: Vite dev proxy в dist не включается.
Не помещать LLM_API_KEY, DATABASE_URL, пароли или Bearer в VITE_*.

Для уже созданного проверочного project параметры сохранены локально:
backend/data/integration_app/environment.private.json; override.yml содержит пароль БД.
Не выводить docker compose config с этими параметрами в общий лог.

~~~powershell
$taskConfig = Get-Content backend/data/integration_app/environment.private.json -Raw | ConvertFrom-Json
$env:INTEGRATION_DEMO_DB_PASSWORD = $taskConfig.INTEGRATION_DEMO_DB_PASSWORD
$env:INTEGRATION_DEMO_PORT = $taskConfig.INTEGRATION_DEMO_PORT
docker compose -p pulse-integration-app-20261025 -f compose.integration-demo.yml -f backend/data/integration_app/override.yml start postgres backend
$env:VITE_BASE_API = ''
$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:58145'
npm --prefix frontend run dev
~~~

Не запускать второй Vite, если 5173 уже занят. Текущий сервер оставлен для просмотра.
Безопасная остановка только этого project:

~~~powershell
docker compose -p pulse-integration-app-20261025 -f compose.integration-demo.yml -f backend/data/integration_app/override.yml stop
~~~

Frontend, запущенный вручную: Ctrl+C. Для фонового проверочного процесса сначала
сверить PID из backend/data/integration_app/runtime.json с CommandLine,
содержащим путь именно этого worktree; только затем остановить этот PID.
Тома и сети сохранять.

## Проверки

- TypeScript: passed.
- Полный frontend Vitest: 136 passed, 28 файлов.
- Новые проверки: реальный контракт login/me/Bearer через fake HTTP, 204 logout,
  отказ без локального fallback, restore/expiry, запоздалый 401,
  устаревшие thunk-ответы, actor-scoped capabilities, смена компании из карточки,
  отсутствие выдуманного publisher/валюты, financial review 16 UNKNOWN + 4 NEEDS_REVIEW.
- После устранения act-предупреждений затронутые 5 тестов повторены: passed.
- Backend: 80 passed (auth_unit, auth_capabilities_unit, auth_docker_smoke,
  source_provenance, docker_demo), SDK заблокирован тестовым conftest.
- Vite production build: passed.
- Lint изменённых TS/TSX: passed; форматирование проверяется отдельно.
- 42 реальных HTTP-проверки через proxy и прямой CORS backend: passed.
- Проверены конкретные OpenAPI маршруты/security/responses, а не число путей.
- Полная PostgreSQL/backend-регрессия всех модулей в этой интеграции не запускалась:
  backend не изменён. Реальный E2E использует отдельную PostgreSQL с migrations/seed.
- Повторные локальные login-проверки достигли 429 (5 входов/логин/15 минут);
  throttle не отключался. После планового перезапуска только собственного backend
  итоговый HTTP-набор выполнен одним проходом. In-memory limiter сбрасывается
  при рестарте процесса — существующее ограничение, не production-ready shared limiter.
- 0 LLM-вызовов; 0 jobs/attempts подтверждены запросом к собственной БД.

HTTP: health/ready/docs/OpenAPI/login/me/profile/feed/detail/capabilities — 200;
пустой feed — items=[]; без токена/неверный пароль/отозванный токен — 401;
чужая компания/карточка/неизвестный идентификатор — 403 (скрытие существования);
logout — 204 и пустое тело; CORS Authorization для localhost:5173 — 200.
Same-origin Vite preflight может отвечать 204; это не ответ backend CORS.

Браузер: login A, выбор DEMO-001/003, профиль, summary, feed, detail,
пустой feed, выключенный analysis submit, logout, login B только DEMO-002,
его карточка, refresh с /api/me, профиль, статус, account, logout,
Back после logout остаётся на login. Итоговая вкладка: console warn/error=[].
После правки Vite config потребовался перезапуск собственного dev-процесса;
в одной старой IAB-вкладке сохранилась ERR_CONNECTION_REFUSED. Свежая вкладка
и последующий refresh работали. Не считать это доказательством устойчивости deployment.

## Охват 12 экранов

| Экран | Маршрут/компонент | Реальное подключение | Остаток |
|---|---|---|---|
| Вход | /login, Login | login + me, серверный пароль | нет refresh-token/SSO |
| Главная банка | /, Home | preview инсайтов API | банковские суммы/операции — помеченный mock |
| Сводка | /pulse/summary, PulseSummary | feed выбранной компании | не отдельная server summary |
| Источники | в MVP отсутствует | источники только внутри insight card | каталог/статистика/API не добавлялись |
| Лента | /pulse/insights, Insights | paginated company feed | фильтры/избранное/hide локальные |
| Карточка | /pulse/insights/:insightId, Insight | detail + sources/evidence/validation | нет QA-chat, экспертной верификации |
| История | в MVP отсутствует | отсутствует | lifecycle прогнозов не реализован |
| Своя новость | /pulse/insights/new, AnalyzeNews | readiness + company capabilities | demo BLOCKED, не выполнялся POST анализа |
| Профиль | /pulse/company/profile, CompanyProfile | company profile API | edit не реализован |
| Контекст/файлы | в MVP отсутствует | отсутствует | upload/обработка не реализованы |
| Настройки | в MVP отсутствует | отсутствует | preferences/notification API не реализованы |
| Аккаунт | /pulse/company/account, Account | server identity + logout | смена пароля/восстановление не реализованы |

Дополнительная страница /pulse/company/status показывает health/readiness/OpenAPI.
OpenAPI backend пока объявляет version=1.22.1; это метаданные существующего f4ca5b5,
не номер фактически интегрированной версии. Требует отдельной согласованной правки.

## Остаток и приоритеты

1. Для demo достаточно проверенного read-only сценария; не включать AI или внешний DB-контекст.
2. Favorites, hide, сортировка и фильтры сохраняются локально по login+company,
   не синхронизируются с сервером/устройствами. Счётчики относятся к загруженной части feed.
3. Будущий server favorites/hide API должен использовать existing ACL, затем frontend contract tests.
4. Sources/history/context/settings отсутствуют в сокращённой MVP-ветке; это отдельные
   вертикальные срезы, не интеграционные ошибки уже работающих страниц.
5. SessionStorage доступен JS: XSS защита/CSP и production reverse proxy требуют отдельной проверки.
   Нельзя объявлять этот локальный demo полноценной банковской авторизацией.
6. Вторичный анализ других компаний сохраняет старую обработку API-ошибок; в read-only demo
   он недостижим после успешного нового анализа. Перед разрешением анализа нужен отдельный
   вертикальный срез capability per target + write ACL, без автоматического retry.
7. Financial reviewer эвристический. UNKNOWN/NEEDS_REVIEW не означают доказанную ложность.
   PREPARATION_FAILED остаётся нерешённым диагностическим вопросом; повтор не добавлен.

## Отдельное предложение: показ первого реального пилота

Не реализовано и не импортировалось автоматически.
После согласования: однократно экспортировать только allowlisted сохранённый
синтетический DTO/analysis/evidence/review, проверить fixture SHA-256 и отсутствие
секретов, зарегистрировать read-only демонстрационную запись в собственной demo БД
через обычные grants/ACL. Существующие pilot-артефакты и исходную БД не изменять.
Не создавать новый job, не вызывать SDK, не подменять seed-записи молча.

В UI обязательны: «Синтетический пилот», дата/модель, сведения о технических
проверках отдельно от качества; 16 UNKNOWN и 4 NEEDS_REVIEW видимы,
финансовая достоверность не подтверждена. 2395 токенов и 15,688 с — только
сведения одного сохранённого опыта, не гарантия качества/скорости.
Это требует отдельного согласования импорта и перечня экспортируемых полей.

## Изменённые frontend-файлы относительно 07e5bb3

- frontend/.env.example
- frontend/docs/DATA_STAND.md
- frontend/docs/DEPLOY.md
- frontend/src/App.tsx
- frontend/src/hooks/useCompanyCapabilities.test.tsx
- frontend/src/hooks/useCompanyCapabilities.ts
- frontend/src/hooks/useCompanyProfiles.ts
- frontend/src/pages/AnalyzeNews.test.tsx
- frontend/src/pages/AnalyzeNews.tsx
- frontend/src/pages/Home.tsx
- frontend/src/pages/Insight.tsx
- frontend/src/pages/Login.test.tsx
- frontend/src/pages/Login.tsx
- frontend/src/pages/ServiceStatus.tsx
- frontend/src/shared/api/apiErrors.ts
- frontend/src/shared/api/auth.api.ts
- frontend/src/shared/api/mappers/companyMappers.test.ts
- frontend/src/shared/api/mappers/companyMappers.ts
- frontend/src/shared/api/mappers/pulseMappers.test.ts
- frontend/src/shared/api/mappers/pulseMappers.ts
- frontend/src/shared/api/request.ts
- frontend/src/shared/auth/RequireAuth.tsx
- frontend/src/shared/auth/SessionBootstrap.tsx
- frontend/src/shared/auth/session.ts
- frontend/src/store/models/IPulse.ts
- frontend/src/store/reducers/AuthSlice.ts
- frontend/src/store/reducers/CompanySlice.ts
- frontend/src/store/rootReducer.ts
- frontend/src/store/selectors/pulse.ts
- frontend/src/store/service/Auth/signIn.test.ts
- frontend/src/store/service/Auth/signIn.ts
- frontend/src/store/sessionScopeMiddleware.ts
- frontend/src/store/store.ts
- frontend/src/test/renderWithStore.tsx
- frontend/src/test/setup.ts
- frontend/src/widgets/Account/LogoutDialog.test.tsx
- frontend/src/widgets/Account/LogoutDialog.tsx
- frontend/src/widgets/Company/CompanyFields.test.tsx
- frontend/src/widgets/Company/CompanyFields.tsx
- frontend/src/widgets/Insight/InsightSections.tsx
- frontend/src/widgets/Insight/InsightSidePanel.tsx
- frontend/src/widgets/Layout/AlfaHeader.test.tsx
- frontend/src/widgets/Layout/AlfaHeader.tsx
- frontend/vite.config.ts


## Фиксация интеграции v1.25.0

Повторная проверка перед локальным коммитом: TypeScript passed;
136 frontend tests passed (28 файлов, без act-предупреждений);
80 backend tests passed; Vite production build passed.
Повторный платный запрос, импорт реального пилота и запись в PostgreSQL не выполнялись.
Полный backend suite не запускался; backend и миграции в этом срезе не менялись.
Lint/Prettier изменённых TS/TSX и git diff --cached --check проверяются до коммита.

Состав: 165 файлов frontend, включая снимок исходной MVP-ветки
и 44 интеграционных изменения, плюс этот отчёт. Всего 166 файлов.
node_modules, dist, backend/data, пароли и токены не входят.
Исходные ветки не переписывались; перенос снимка frontend не создаёт merge-parent
и не заменяет будущего согласования Git-истории с frontend-командой.

### Полный перечень файлов коммита

- docs/FRONTEND_BACKEND_INTEGRATION.md
- frontend/.env.example
- frontend/.gitattributes
- frontend/.gitignore
- frontend/.prettierignore
- frontend/.prettierrc
- frontend/components.json
- frontend/docs/DATA_STAND.md
- frontend/docs/DEPLOY.md
- frontend/eslint.config.js
- frontend/index.html
- frontend/package-lock.json
- frontend/package.json
- frontend/postcss.config.js
- frontend/public/favicon.svg
- frontend/src/App.tsx
- frontend/src/assets/alfa-logo.png
- frontend/src/components/ui/button-variants.ts
- frontend/src/components/ui/button.tsx
- frontend/src/components/ui/calendar.tsx
- frontend/src/components/ui/dialog.tsx
- frontend/src/components/ui/popover.tsx
- frontend/src/components/ui/select.tsx
- frontend/src/components/ui/sheet.tsx
- frontend/src/components/ui/skeleton.tsx
- frontend/src/components/ui/toast.tsx
- frontend/src/components/ui/toaster.tsx
- frontend/src/hooks/useCompanyCapabilities.test.tsx
- frontend/src/hooks/useCompanyCapabilities.ts
- frontend/src/hooks/useCompanyProfiles.ts
- frontend/src/hooks/useFavorites.ts
- frontend/src/hooks/useFeedPolling.ts
- frontend/src/hooks/useInsightCard.ts
- frontend/src/hooks/usePulseData.ts
- frontend/src/hooks/useReadiness.ts
- frontend/src/hooks/useScrollTopOnNavigate.ts
- frontend/src/hooks/useServiceStatus.test.ts
- frontend/src/hooks/useServiceStatus.ts
- frontend/src/hooks/useToast.test.tsx
- frontend/src/hooks/useToast.ts
- frontend/src/index.css
- frontend/src/lib/utils.ts
- frontend/src/main.tsx
- frontend/src/pages/Account.tsx
- frontend/src/pages/AnalyzeNews.test.tsx
- frontend/src/pages/AnalyzeNews.tsx
- frontend/src/pages/CompanyProfile.tsx
- frontend/src/pages/Home.tsx
- frontend/src/pages/Insight.tsx
- frontend/src/pages/Insights.test.tsx
- frontend/src/pages/Insights.tsx
- frontend/src/pages/Login.test.tsx
- frontend/src/pages/Login.tsx
- frontend/src/pages/NotFound.tsx
- frontend/src/pages/PulseSummary.tsx
- frontend/src/pages/ServiceStatus.tsx
- frontend/src/routes.tsx
- frontend/src/shared/api/apiErrors.ts
- frontend/src/shared/api/auth.api.ts
- frontend/src/shared/api/companies.api.ts
- frontend/src/shared/api/insights.api.ts
- frontend/src/shared/api/mappers/companyMappers.test.ts
- frontend/src/shared/api/mappers/companyMappers.ts
- frontend/src/shared/api/mappers/pulseMappers.test.ts
- frontend/src/shared/api/mappers/pulseMappers.ts
- frontend/src/shared/api/news.api.test.ts
- frontend/src/shared/api/news.api.ts
- frontend/src/shared/api/request.test.ts
- frontend/src/shared/api/request.ts
- frontend/src/shared/api/system.api.test.ts
- frontend/src/shared/api/system.api.ts
- frontend/src/shared/auth/RequireAuth.tsx
- frontend/src/shared/auth/SessionBootstrap.tsx
- frontend/src/shared/auth/session.ts
- frontend/src/shared/constants/accounts.test.ts
- frontend/src/shared/constants/accounts.ts
- frontend/src/shared/constants/companies.ts
- frontend/src/shared/constants/insights.ts
- frontend/src/shared/constants/toast.ts
- frontend/src/shared/mocks/bank.ts
- frontend/src/shared/storage/storage.ts
- frontend/src/shared/ui/AlfaLogo.tsx
- frontend/src/shared/ui/BackLink.tsx
- frontend/src/shared/ui/Card.tsx
- frontend/src/shared/ui/DatePickerInput.tsx
- frontend/src/shared/ui/DemoStub.tsx
- frontend/src/shared/ui/LayerTag.tsx
- frontend/src/shared/ui/PageLoader.tsx
- frontend/src/shared/ui/PulseLogo.tsx
- frontend/src/shared/ui/Segmented.test.tsx
- frontend/src/shared/ui/Segmented.tsx
- frontend/src/shared/ui/Tag.tsx
- frontend/src/shared/ui/TimePickerInput.tsx
- frontend/src/shared/ui/appToast.ts
- frontend/src/shared/ui/fieldStyles.ts
- frontend/src/shared/ui/tagTones.ts
- frontend/src/shared/utils/dateTimeInput.test.ts
- frontend/src/shared/utils/dateTimeInput.ts
- frontend/src/shared/utils/plural.test.ts
- frontend/src/shared/utils/plural.ts
- frontend/src/store/hooks/redux.ts
- frontend/src/store/models/ICompany.ts
- frontend/src/store/models/IInsight.ts
- frontend/src/store/models/INews.ts
- frontend/src/store/models/IPulse.ts
- frontend/src/store/reducers/AnalysisSlice.test.ts
- frontend/src/store/reducers/AnalysisSlice.ts
- frontend/src/store/reducers/AuthSlice.ts
- frontend/src/store/reducers/CompanySlice.test.ts
- frontend/src/store/reducers/CompanySlice.ts
- frontend/src/store/reducers/InsightsSlice.test.ts
- frontend/src/store/reducers/InsightsSlice.ts
- frontend/src/store/reducers/PulseSlice.test.ts
- frontend/src/store/reducers/PulseSlice.ts
- frontend/src/store/rootReducer.ts
- frontend/src/store/selectors/pulse.ts
- frontend/src/store/service/Auth/signIn.test.ts
- frontend/src/store/service/Auth/signIn.ts
- frontend/src/store/service/Company/getCompanyProfile.ts
- frontend/src/store/service/Insights/getInsightsFeed.ts
- frontend/src/store/service/Insights/refreshInsightsFeed.test.ts
- frontend/src/store/service/Insights/refreshInsightsFeed.ts
- frontend/src/store/service/Insights/runAnalysis.ts
- frontend/src/store/sessionScopeMiddleware.ts
- frontend/src/store/store.ts
- frontend/src/store/types.ts
- frontend/src/test/renderWithStore.tsx
- frontend/src/test/setup.ts
- frontend/src/vite-env.d.ts
- frontend/src/widgets/Account/LogoutDialog.test.tsx
- frontend/src/widgets/Account/LogoutDialog.tsx
- frontend/src/widgets/Analysis/AiDemoNotice.tsx
- frontend/src/widgets/Analysis/OtherCompaniesAnalysis.tsx
- frontend/src/widgets/Company/AboutCompany.tsx
- frontend/src/widgets/Company/CompanyFields.test.tsx
- frontend/src/widgets/Company/CompanyFields.tsx
- frontend/src/widgets/Home/BankOverview.tsx
- frontend/src/widgets/Home/PulseWidget.tsx
- frontend/src/widgets/Insight/InsightSections.tsx
- frontend/src/widgets/Insight/InsightSidePanel.tsx
- frontend/src/widgets/Insights/FeedStates.tsx
- frontend/src/widgets/Insights/InsightCard.tsx
- frontend/src/widgets/Insights/InsightKindTag.tsx
- frontend/src/widgets/Insights/feedFilter.test.ts
- frontend/src/widgets/Insights/feedFilter.ts
- frontend/src/widgets/Insights/insightView.test.ts
- frontend/src/widgets/Insights/insightView.ts
- frontend/src/widgets/Layout/AlfaHeader.test.tsx
- frontend/src/widgets/Layout/AlfaHeader.tsx
- frontend/src/widgets/Layout/AlfaLayout.tsx
- frontend/src/widgets/Layout/AlfaSidebar.tsx
- frontend/src/widgets/Layout/CompanyLayout.tsx
- frontend/src/widgets/Layout/DemoStubs.test.tsx
- frontend/src/widgets/Layout/MobileMenu.test.tsx
- frontend/src/widgets/Layout/MobileMenu.tsx
- frontend/src/widgets/Layout/NotificationsBell.tsx
- frontend/src/widgets/Layout/PageHeading.tsx
- frontend/src/widgets/Layout/PulseLayout.tsx
- frontend/src/widgets/Layout/ServiceStatusBanner.tsx
- frontend/src/widgets/Layout/config.ts
- frontend/tailwind.config.ts
- frontend/tsconfig.app.json
- frontend/tsconfig.json
- frontend/tsconfig.node.json
- frontend/tsconfig.test.json
- frontend/vite.config.ts
