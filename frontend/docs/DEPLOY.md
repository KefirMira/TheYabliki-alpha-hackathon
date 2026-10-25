# Интеграционное синтетическое демо

Актуальная инструкция: [FRONTEND_BACKEND_INTEGRATION.md](../../docs/FRONTEND_BACKEND_INTEGRATION.md).
Работать из worktree ветки integration/frontend-backend.

Используется compose.integration-demo.yml и настоящий серверный login с паролем.
Старый compose.frontend.yml не создаёт необходимые персональные аккаунты.
VITE_DEMO_ACCOUNTS и произвольный логин больше не предоставляют доступ:
компании определяются исключительно ответом /api/me.

Нужны Node.js 24, npm 11, Docker Desktop (Linux containers), Compose v2.

1. Создать отдельное backend-окружение и выполнить защищённый seed по
   [INTEGRATION_DEMO.md](../../docs/INTEGRATION_DEMO.md). Вводить два независимых
   пароля интерактивно; не помещать их в frontend/.env или VITE_*.
2. Запустить frontend из корня:

~~~powershell
$env:VITE_BASE_API = ''
$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:8000'
npm --prefix frontend ci
npm --prefix frontend run dev
~~~

Открыть http://127.0.0.1:5173. Вход: synthetic-demo-a или synthetic-demo-b,
пароль — заданный при seed. DEMO-001/003 доступны первому, DEMO-002 — второму.

Dev proxy направляет /api, /health, /ready, /docs, /openapi.json в backend.
Ни ключ LLM, ни DATABASE_URL frontend не нужны. Production-сборке необходим
same-origin reverse proxy для этих путей; Vite proxy работает только в dev.

Проверки: npm --prefix frontend run typecheck; npm --prefix frontend run test:run;
npm --prefix frontend run build.

Остановка backend: docker compose -p <свой-project> -f compose.integration-demo.yml stop.
Frontend: Ctrl+C в терминале запуска. Не удалять тома или чужие ресурсы.
