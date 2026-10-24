# Стенд с данными кейса

Отдельный от демо стенд для показа на настоящих компаниях кейса: своя
PostgreSQL `test_pulse_data` и бэкенд в Docker
([compose.data.yml](../../compose.data.yml)), фронт — dev-сервер Vite на
localhost. С демо-стендом (`pulse-frontend-demo`) не пересекается: другой
проект, том, сеть и порт бэкенда.

CSV кейса — закрытые данные хакатона: не кладите их в Git, не монтируйте в
контейнеры стенда и не публикуйте выгрузки БД. Импорт выполняется одноразовым
контейнером, файлы подключаются только на чтение.

## 1. Поднять стенд с пустой базой

Из корня репозитория:

```bash
docker compose -p pulse-data -f compose.data.yml up -d --build --wait --wait-timeout 300
```

Бэкенд: `http://localhost:8002` (`DATA_BACKEND_PORT`), CORS разрешён для
`localhost:5173`.

Фронт — dev-сервер Vite в режиме `data`: он берёт `frontend/.env`, а поверх —
`frontend/.env.data` с адресом этого бэкенда и компаниями стенда. Файл в Git
не попадает (`.env.*` в `.gitignore`), создайте его один раз:

```bash
cat > frontend/.env.data <<'EOF'
VITE_BASE_API=http://localhost:8002
VITE_DEMO_COMPANY_IDS=U_102920,U_212846,U_26030,U_34911,U_177581
VITE_DEMO_ACCOUNTS=expert=U_102920,U_212846,U_26030,U_34911,U_177581;group=U_102920,U_212846;fuel=U_26030;agro=U_34911;stroy=U_177581
EOF
npm --prefix frontend run dev:data
```

Фронт откроется на `http://localhost:5173`. Обычный `npm run dev` по-прежнему
работает с демо-стендом.

При первом запуске PostgreSQL применяет `schema.sql` и миграции 002–006, а
затем ставит метку `pulse:isolated-company-import:v1`. Без этой метки
импортёры отказываются писать в базу. Демо-фикстур в этой базе нет.

## 2. Проверить файлы (dry-run, без базы)

Импортёры проверяют файлы, ничего не записывая. Отчёт содержит только
количества и номера строк, без значений.

```bash
DATA_DIR='B:/progfile/xacaton/other/Данные для участников'
MSYS_NO_PATHCONV=1 docker run --rm --network none \
  -v "$PWD/backend:/src:ro" -v "$DATA_DIR:/data:ro" -w /src \
  pulse-data-backend python -m company_import --file /data/df_Uid_data_hack.csv
```

Результат проверки 24.10.2026:

| Файл      | Строк     | Прошли    | Отклонены                                |
| --------- | --------- | --------- | ---------------------------------------- |
| Профили   | 85 525    | 85 513    | 12 — все строки одного конфликтного `U_` |
| Платежи   | 1 380 585 | 1 380 585 | 0                                        |
| Связи F–U | 12 514    | 12 514    | 0                                        |

## 3. Импорт

**Требует отдельного разрешения: это запись закрытых данных хакатона.** Порядок
обязательный: сначала профили, затем платежи и связи. Контейнер импорта
подключается к сетевому пространству PostgreSQL стенда, поэтому адрес базы —
`127.0.0.1:5432`: импортёры принимают только loopback. DSN передаётся через
переменную окружения, а не аргументом команды.

```bash
DATA_DIR='B:/progfile/xacaton/other/Данные для участников'
export COMPANY_IMPORT_DATABASE_URL='postgresql+asyncpg://pulse_data:pulse_local_data_only@127.0.0.1:5432/test_pulse_data'
export DATASET_IMPORT_DATABASE_URL="$COMPANY_IMPORT_DATABASE_URL"
# Массив, а не строка: в пути к данным есть пробелы («Данные для участников»),
# и строка при раскрытии разбилась бы на лишние аргументы -v.
RUN=(docker run --rm --network container:pulse-data-postgres-1
  -v "$PWD/backend:/src:ro" -v "$DATA_DIR:/data:ro" -w /src
  -e COMPANY_IMPORT_DATABASE_URL -e DATASET_IMPORT_DATABASE_URL
  pulse-data-backend)

# Профили: 12 конфликтных строк исключаются, остальные записываются.
MSYS_NO_PATHCONV=1 "${RUN[@]}" python -m company_import --file /data/df_Uid_data_hack.csv \
  --apply --confirm-isolated-import --target isolated \
  --expected-database test_pulse_data --allow-partial

# Платежи и связи: любая ошибочная строка блокирует весь файл.
MSYS_NO_PATHCONV=1 "${RUN[@]}" python -m dataset_import payments --file /data/df_Uid_payment_hack.csv \
  --apply --confirm-isolated-import --target isolated --expected-database test_pulse_data
MSYS_NO_PATHCONV=1 "${RUN[@]}" python -m dataset_import links --file /data/df_Fid_Uid_link_hack.csv \
  --apply --confirm-isolated-import --target isolated --expected-database test_pulse_data
```

Профили пишутся одной транзакцией, на 85 тысяч строк уходит несколько минут.
Платежи импортируются со скоростью около 4,5 тысячи строк в секунду. Повтор
той же команды безопасен: изменений не будет (`created=0`, `unchanged` равно
числу строк).

Импорт 24.10.2026 на этой машине: профили — 85 513 за 1 мин 20 с, платежи —
1 380 585 за 2,5 мин, связи — 12 514. Ошибок нет, итог совпал с dry-run.

## 4. Что увидит пользователь

- **Тестовые логины** (`VITE_DEMO_ACCOUNTS` в `.env.data`), пароль не
  проверяется:

  | Логин    | Компании                             |
  | -------- | ------------------------------------ |
  | `expert` | все пять                             |
  | `group`  | `U_102920`, `U_212846` — одна группа |
  | `fuel`   | `U_26030`                            |
  | `agro`   | `U_34911`                            |
  | `stroy`  | `U_177581`                           |

- **Компании в шапке** заданы переменной `VITE_DEMO_COMPANY_IDS` в `.env.data`.
  Это клиенты целевого сегмента (выручка больше 15 млрд ₽), подобранные под
  темы аналитики:

  | ID                     | Чем занимается                                      | Зачем в демо                                |
  | ---------------------- | --------------------------------------------------- | ------------------------------------------- |
  | `U_102920`, `U_212846` | Опт продуктами (импорт рыбы и фруктов), опт неспец. | Одна группа: один логин, несколько компаний |
  | `U_26030`              | Опт моторным топливом, Башкортостан, ВЭД            | Топливный рынок, пошлины, ставка            |
  | `U_34911`              | Опт зерном, Ростов, экспорт                         | Агроэкспорт, курс рубля                     |
  | `U_177581`             | Строительство зданий, Москва, крупная группа        | Ключевая ставка, ипотека, стройка           |

- **Названия.** В CSV настоящих названий нет. API отдаёт `name=null`, и в шапке
  вместо названия виден идентификатор `U_…`. Это честное поведение, ничего не
  придумывается.
- **Лента пустая**, пока не включён ИИ (этап 2). Профиль компании уже
  показывает отрасль, регион, выручку и статус клиента.
- **Корпус RAG** (OCR-JSON аналитики банка) в Git не входит и на этой машине
  отсутствует. Для полного режима его нужно положить в том `pulse-data_data_rag`
  или подключить через `RAG_CORPUS_DIR`.

## Остановить и удалить

```bash
docker compose -p pulse-data -f compose.data.yml stop
```

Чтобы удалить базу с импортированными данными, остановите проект и удалите том
`pulse-data_data_pgdata`. Это необратимо, повторный импорт займёт минуты.
