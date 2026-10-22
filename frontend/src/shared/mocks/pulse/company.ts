/** Демо-данные вкладки «Моя компания» из макетов v6. */

export type FieldSource = 'bank' | 'calc' | 'pay' | 'file' | 'user'

export interface ICompanyField {
  key: string
  label: string
  value: string
  source: FieldSource
}

export const COMPANY_NAME = 'ООО «Демо Топливо»'

export const COMPANY_DESCRIPTION =
  'Оптовая торговля моторным топливом с центром в Уфе. Закупки сосредоточены у нескольких крупных поставщиков. Основные покупатели — топливные трейдеры и строительные компании, работающие на железнодорожных и метростроевских объектах. Есть кредит и лизинг в Альфа-Банке, внешнеэкономические операции с Грузией, Латвией и Польшей.'

export const COMPANY_FIELDS: ICompanyField[] = [
  {
    key: 'ind',
    label: 'Отрасль',
    value:
      'ОКВЭД 46.71.2 — Торговля оптовая моторным топливом, включая авиационный бензин',
    source: 'bank',
  },
  {
    key: 'pos',
    label: 'Положение в отрасли',
    value:
      '№2 по выручке среди 910 компаний отрасли · ≈4,6% их совокупной выручки',
    source: 'calc',
  },
  {
    key: 'scale',
    label: 'Масштаб',
    value: 'Выручка 60,4 млрд ₽ · 16–100 сотрудников',
    source: 'bank',
  },
  {
    key: 'prod',
    label: 'Продукты в Альфа-Банке',
    value: 'РКО, кредит, лизинг',
    source: 'bank',
  },
  {
    key: 'ved',
    label: 'ВЭД',
    value: 'Страны в данных ФТС: Грузия, Латвия, Польша',
    source: 'bank',
  },
  {
    key: 'buy',
    label: 'Покупатели',
    value:
      '237 контрагентов · топ-5 — 79% поступлений · 26% — строительство железных дорог и метро',
    source: 'pay',
  },
  {
    key: 'sup',
    label: 'Поставщики',
    value: '112 контрагентов · топ-5 — 96% платежей',
    source: 'pay',
  },
  {
    key: 'region',
    label: 'Регион',
    value: 'Уфа, Республика Башкортостан',
    source: 'bank',
  },
  {
    key: 'stage',
    label: 'Стадия развития',
    value: 'Оптимизация · 8–15 лет на рынке',
    source: 'bank',
  },
  { key: 'own', label: 'Собственность', value: 'Частная', source: 'bank' },
]

export type FileStatus = 'done' | 'processing' | 'error'

export interface IContextFile {
  id: string
  name: string
  meta: string
  status: FileStatus
  /** Итог разбора, прогресс или текст ошибки. */
  note?: string
  progress?: number
}

export const CONTEXT_FILES: IContextFile[] = [
  {
    id: 'f1',
    name: 'Кредитный портфель.xlsx',
    meta: 'Сегодня, 10:14 · 248 КБ',
    status: 'done',
    note: 'Найдено 2 договора: кредитная линия (плавающая ставка, КС + 2,1%) и лизинг техники',
  },
  {
    id: 'f2',
    name: 'Покупатели_топ.csv',
    meta: 'Сегодня, 10:16 · 56 КБ',
    status: 'processing',
    progress: 64,
  },
  {
    id: 'f3',
    name: 'Стратегия.pdf',
    meta: 'Сегодня, 10:02 · 4,6 МБ',
    status: 'error',
    note: 'Не удалось распознать текст. Загрузите файл с текстовым слоем',
  },
]

/** Шаблоны CSV для загрузки контекста — формат задаём сами. */
export const CONTEXT_TEMPLATES = [
  {
    label: 'Кредитный портфель (CSV)',
    file: 'kreditnyi-portfel.csv',
    header: 'договор;банк;тип;сумма_руб;ставка;плавающая_ставка;дата_окончания',
  },
  {
    label: 'Ключевые контрагенты (CSV)',
    file: 'klyuchevye-kontragenty.csv',
    header: 'название;инн;роль;доля_в_оборотах;отрасль',
  },
  {
    label: 'Валютные контракты (CSV)',
    file: 'valyutnye-kontrakty.csv',
    header: 'контрагент;страна;валюта;сумма;направление;товар',
  },
]

export const CONTEXT_NOTES =
  'Поставщики — 3 НПЗ Поволжья и Урала. Ключевые покупатели — подрядчики РЖД и метростроя. Планируем расширить лизинг техники в 2027 г.'

export const API_DATA_TYPES = [
  'Контрагенты',
  'Договоры',
  'Кредиты',
  'Валютные контракты',
  'Планы',
]

export const API_SAMPLE = `{
  "counterparty": "ООО «УралСтройПуть»",
  "role": "buyer",
  "share": 0.12
}`

export const ROLE_SPHERES = [
  'Стратегия',
  'Финансы',
  'Казначейство',
  'Налоги и учёт',
  'ВЭД',
  'Закупки и поставки',
]

export interface IPersonalData {
  lastName: string
  firstName: string
  middleName: string
  birthDate: string
  phone: string
  email: string
}

export const DEMO_USER: IPersonalData = {
  lastName: 'Соколова',
  firstName: 'Ирина',
  middleName: 'Андреевна',
  birthDate: '14.05.1984',
  phone: '+7 916 482-42-18',
  email: 'i.sokolova@demo-toplivo.ru',
}

export const PASSWORD_CHANGED_AT = '12 марта 2026'

export const DIGEST_TIMES = ['07:00', '08:00', '09:00', '10:00', '12:00']
