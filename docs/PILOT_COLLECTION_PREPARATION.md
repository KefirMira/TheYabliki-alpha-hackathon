> Подготовительный исторический отчёт. Генерация восьми ответов и интеграция завершены; актуальные результаты — в [SAVED_PILOT_COLLECTION.md](SAVED_PILOT_COLLECTION.md).

# Подготовка коллекции saved-pilot — v1.29.0 (без реальных запросов)

База: опубликованная v1.28.2. Срез не закоммичен. Новых платных запросов: 0.
Восемь новых ответов пока отсутствуют. Fake SDK выдаёт только технические тестовые
ответы с меткой FAKE_TEST_ONLY; они НЕ добавляются в публичный saved-pilot.
Поэтому обычный Docker-запуск пока честно показывает один прежний реальный результат.

## Входы, модель и ограничения

- Модель: deepseek/deepseek-v4.1-flash; основной https://changellenge.up.railway.app/v1.
- Один запрос на сценарий; для первого пилота предлагается только metal-rate.
- Вход до 8000 (локальная консервативная байтовая оценка, не tokenizer провайдера).
- max_tokens=2000, включая reasoning; SDK 60 секунд, операция 120 секунд.
- max_retries=0, redirect/fallback/tools отсутствуют. Неизвестный исход не повторять.
- Для всех восьми сумма input allowances: 37916.
- С выходом до 16000 суммарная плановая граница этих конкретных payload: 53916. Это не денежная гарантия.
- Ориентир реального usage: 20–32 тыс. токенов на восемь; окончательный usage неизвестен.
- Тариф шлюза не опубликован/не подтверждён. RUB/USD стоимость null; общий лимит команды не является выделенным бюджетом.

## Восемь сценариев и источники

| Сценарий | Компания | Публичные исторические источники |
|---|---|---|
| metal-rate — Металлургия: ужесточение денежно-кредитных условий | SYNTH-COLLECTION-METAL | [Банк России 2024-10-25](https://www.cbr.ru/press/PR/?file=25102024_133000Key.htm); [Банк России 2024-10-25](https://www.cbr.ru/press/PR/?file=25102024_133000Key.htm) |
| metal-export — Металлургия: ограничения доступа на экспортный рынок | SYNTH-COLLECTION-METAL | [European Commission / DG FISMA 2022-03-15](https://finance.ec.europa.eu/news/ukraine-eu-agrees-fourth-package-restrictive-measures-against-russia-2022-03-15_en) |
| metal-inputs — Металлургия: изменение стоимости сырья | SYNTH-COLLECTION-METAL | [World Bank 2025-04-29](https://www.worldbank.org/en/news/press-release/2025/04/29/commodity-markets-outlook-april-2025-press-release) |
| retail-inflation — Розница: ускорение инфляции | SYNTH-COLLECTION-RETAIL | [Банк России 2024-10-25](https://www.cbr.ru/press/event/?id=21111) |
| retail-demand — Розница: охлаждение потребительского спроса | SYNTH-COLLECTION-RETAIL | [Банк России 2024-10-25](https://www.cbr.ru/press/PR/?file=25102024_133000Key.htm) |
| retail-logistics — Розница: удлинение логистических маршрутов | SYNTH-COLLECTION-RETAIL | [UNCTAD / United Nations Office at Geneva 2024-10-22](https://www.unognewsroom.org/teleprompter/en/2395/unctad-press-conference-22-october-2024/7213) |
| production-fx-equipment — Производство: валютный курс и стоимость оборудования | SYNTH-GATEWAY-MACRO-A | [Банк России 2025-05-12](https://www.cbr.ru/dkp/mp_dec/decision_key_rate/summary_key_rate_12052025/) |
| production-support — Производство: проверка доступа к господдержке | SYNTH-GATEWAY-MACRO-A | [Минтранс России; сообщение о программе Корпорации МСП 2025-03-17](https://mintrans.gov.ru/press-center/branch-news/6436); [Корпорация МСП дата публикации неизвестна](https://corpmsp.ru/to-business/lizingovaya-podderzhka/) |

Все новые новости — явные учебные гипотезы. Публикации 2022–2025 годов не
выдаются за текущие новости 2026 года или факты конкретной компании.
Для динамической страницы Корпорации МСП publication date=null; 17.03.2025 —
отдельная дата события на странице, не придуманная дата публикации.
Сохраняются только короткие проверенные цитаты, URL, издатель, дата/locator и SHA-256.
Имена public-*.txt — локальные текстовые экспорты HTML, page=1 — страница экспорта,
а НЕ номер страницы исходного PDF. Полные страницы, логотипы и закрытые PDF не копируются.
Наличие источника и точность цитаты не доказывают смысловую поддержку вывода модели.
Это не юридический аудит актуальной применимости санкций/субсидий.

## Закрепление

- Канонический SHA-256 inputs: `34b6d9229bd308cecb9b8f716bfb942299e31574e4d7ffb9950f3f19d2e5492f`.
- Канонический SHA-256 preflight: `48d890fa18879a7b5a2bd6bdcfe7e5fa6023e563682225d49582924eed513ed2`.
- Исторический artifact SHA-256 без изменений: `5c75a2d975712f20303c065adaf64d69337d1812cc6738aa49cc23a2c14a243f`.
- Полный pinned JSON: backend/fixtures/pilot_collection_inputs_v1.json.
- Точные сообщения восстанавливаются только make_collection_input(scenario_id);
  verify_collection_input сверяет их digest с отдельным закреплённым preflight.
- Локальный полный состав запросов: ignored backend/data/pilot_collection_preparation/exact-requests.json.

| Сценарий | Input allowance | DTO SHA-256 |
|---|---:|---|
| metal-rate | 5137 | `0e1b5ac3152c69bbf301ba17c236d57004a242cd651c59fff542c83856e8308d` |
| metal-export | 4731 | `c97eb8e40b90172ad3b81d3f1336beb9c7010cdd7a69ba5af789e9a4f43c9574` |
| metal-inputs | 4648 | `4fdea3c82b10b81619a41a8b6f1bb60544b969fa8e86ccd9b3564447c597c847` |
| retail-inflation | 4571 | `610a881c76f70e0b3e552ba86a163f62742f2e3c71a828c81eeb070fd17721c4` |
| retail-demand | 4657 | `67257784b5436b47cc11d6eec7a93b411f091a87d7e1c69b140b51d6a5d66d06` |
| retail-logistics | 4587 | `03c772e45012b4709e6e7adfc3d117e2cc5e99bb5cabe37a93ab4f627b10dee2` |
| production-fx-equipment | 4419 | `7d9ac145b56bbbe8f9ce841ac9609d9947e5ccd0f94ba0192538c337b305c0ea` |
| production-support | 5166 | `2666b99effbe6ded9f8c5159b3cd8af91323260a22a6102931ef5c67b02bb274` |

## Тестовый запуск без SDK и сети

Из корня в PowerShell (Python с зависимостями проекта):

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path
$env:PYTHON_DOTENV_DISABLED = '1'
python -B -m evaluation.pilot_collection --plan
python -B -m evaluation.pilot_collection
```

CLI намеренно не принимает --real. Fake usage и текст не являются реальными токенами/ответами.
Fake результаты и точные запросы сохраняются локально в ignored backend/data.

## Добавочная загрузка и сохранность данных

- Release файла saved_pilot_collection_v1.json нет, RELEASE_SHA256=None.
- Произвольный JSON, непроверенный release или fake record публичный loader отвергает.
- После отдельных разрешённых реальных генераций нужен просмотр экспорта и закрепление release hash.
- Импорт использует прежние таблицы/repositories, один transaction/advisory lock, без DDL.
- Исторический anchor проверяется по исходному тексту/источникам/evidence/reviewer/trace.
  Он никогда не переписывается. Старый общий fingerprint не объявляется валидным после расширения.
- Новые записи проверяются scoped digest, охватывающим result/news/run/evidence.
  Посторонние пользовательские записи не удаляются и не мешают безопасному upgrade.
- Viewer сохраняет старый UUID, пароль и read-only ACL; scope/collision/tamper ведут к отказу.
- Fake-import разрешён только внутренним тестам в UUID test_news_identity_* БД, не в публичной demo-БД.
- Публичные credentials, project/volume, одна команда и default offline режим v1.28.2 сохранены.
- Нет нового endpoint, очереди, retry policy или отключения COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED.

## Перед одним реальным пилотом

Нужны отдельное разрешение на metal-rate с указанным DTO hash, проверка ключа/квоты
без раскрытия секрета и однократный dispatch intent. После ошибки/timeout повтора нет.
После ответа сохраняются неизменный assistant content, выбранные поля SDK envelope,
normalized JSON, request/messages, usage, generation date, evidence, reviewer и trace.
Authorization/headers/ключ и reasoning-текст не входят в экспорт.
Восемь новых настоящих ответов не подменяются заранее подготовленным текстом.

Источники выбраны вручную по allowlist, не ранжированы. score=0.0 в старой
схеме — только обязательный технический placeholder, не достоверность/вероятность;
в сообщения LLM score вообще не передаётся.


## Итог проверок подготовки

- 65 профильных backend-тестов PASS, включая PostgreSQL: 3 компании/9 insights,
  8 конкурентных upgrade (1 добавление набора, 7 неизменных повторов),
  сохранность исторического результата и посторонних данных, ACL и rollback.
- 6 React-тестов PASS: legacy, fake/real labels, даты, HTTPS links и отсутствие ложного bank publisher.
- TypeScript и Docker production build PASS.
- Независимый tracked-only Docker context без .env: новый том, прежний read-only login,
  default 1 исторический insight/2 evidence/all20 findings, repeat seed UNCHANGED.
- Новые fake SDK результаты не являются публичными LLM-ответами и не загружаются default seed.
- Сохранены 7 frozen raw SHA-256, исходные pinned fixture/response, production/submission config.
- Локальный API-ключ присутствует, основной URL и модель совпадают с pin; ключ не раскрывался.
- Никаких LLM-запросов, commit, push, merge. Неизвестная денежная стоимость остаётся null.
