import type {
  IHistoryRow,
  INewsSource,
  PulseFactor,
} from '@/store/models/IPulse'

export const DAY_SUMMARY = {
  meta: '15 сентября, 09:00 · по 12 материалам',
  text: 'Главное сегодня — ставка: ЦБ взял паузу на 14%, Альфа-Банк ждёт её сохранения до конца года. Обслуживание кредита и лизинга компании не подешевеет до 2027 г. Рост цен на бензин может поддержать маржу оптовых поставок.',
}

/**
 * «Что сейчас влияет на компанию»: темы собираются из текущих инсайтов,
 * а не из заранее заданного списка. Новая тема появляется сама.
 */
export interface IFactorTopic {
  factor: PulseFactor
  title: string
  insightIds: string[]
  isNew?: boolean
}

export const FACTOR_TOPICS: IFactorTopic[] = [
  { factor: 'rate', title: 'Ставка ЦБ', insightIds: ['rate'] },
  { factor: 'fuel', title: 'Топливо', insightIds: ['fuel', 'supp'] },
  { factor: 'dem', title: 'Бюджет и инфраструктура', insightIds: ['budget'] },
  { factor: 'reg', title: 'Ограничения ЕС', insightIds: ['eu'], isNew: true },
]

export const FACTOR_LABELS: Record<PulseFactor, string> = {
  rate: 'Ставка ЦБ',
  fuel: 'Топливо',
  cp: 'Контрагенты',
  dem: 'Бюджет и спрос',
  reg: 'Регулирование',
  fx: 'Курсы валют',
}

export const SOURCE_STATS = [
  { value: '248', label: 'новостей собрано за сутки' },
  { value: '12', label: 'источников' },
  { value: '61', label: 'дубль удалён' },
  { value: '3', label: 'материала исключены как устаревшие' },
]

export const NEWS_SOURCES: INewsSource[] = [
  {
    name: 'ЦМА Альфа-Банка',
    description: 'Центр макроэкономического анализа',
    type: 'bank',
    materials: 34,
    updated: '2 ч назад',
  },
  {
    name: 'Бонд Бриф',
    description: 'Обзоры долгового рынка Альфа-Банка',
    type: 'bank',
    materials: 8,
    updated: '1 д назад',
  },
  {
    name: 'Макростатистика',
    description: 'Росстат и Банк России, сводные данные',
    type: 'stat',
    materials: 21,
    updated: '1 д назад',
  },
  {
    name: 'Банк России',
    description: 'Пресс-релизы и решения по ставке',
    type: 'reg',
    materials: 6,
    updated: '3 д назад',
  },
  {
    name: 'Минэнерго',
    description: 'Сообщения о рынке нефтепродуктов',
    type: 'reg',
    materials: 4,
    updated: '4 д назад',
  },
  {
    name: 'Товарная биржа',
    description: 'Котировки нефтепродуктов',
    type: 'mkt',
    materials: 9,
    updated: '15 мин назад',
  },
  {
    name: 'Интерфакс',
    description: 'Лента новостей',
    type: 'media',
    materials: 52,
    updated: '5 мин назад',
  },
  {
    name: 'РБК',
    description: 'Экономика и бизнес',
    type: 'media',
    materials: 41,
    updated: '12 мин назад',
  },
  {
    name: 'Ведомости',
    description: 'Экономика и бизнес',
    type: 'media',
    materials: 29,
    updated: '40 мин назад',
  },
  {
    name: 'Коммерсантъ',
    description: 'Экономика и бизнес',
    type: 'media',
    materials: 22,
    updated: '1 ч назад',
  },
  {
    name: 'Reuters',
    description: 'Международные новости',
    type: 'media',
    materials: 15,
    updated: '5 мин назад',
  },
  {
    name: 'ТАСС',
    description: 'Лента новостей',
    type: 'media',
    materials: 7,
    updated: '2 ч назад',
  },
]

export const HISTORY_ROWS: IHistoryRow[] = [
  {
    insightId: 'hist6',
    date: '07.09',
    outcome: 'expired',
    reason: 'Макростатистика 7М26 · 07.09',
  },
  {
    insightId: 'hist4',
    date: '26.08',
    outcome: 'confirmed',
    reason: 'Бензин +0,91% за 25–31 августа',
  },
  {
    insightId: 'hist2',
    date: '26.08',
    outcome: 'updated',
    reason: '',
    updatedInsightId: 'fuel',
  },
  {
    insightId: 'hist5',
    date: '14.08',
    outcome: 'unchecked',
    reason: 'Срок вышел, данных нет',
  },
  {
    insightId: 'hist3',
    date: '31.07',
    outcome: 'refuted',
    reason: 'ЦБ сохранил ставку 14% 11.09',
  },
  {
    insightId: 'hist1',
    date: '31.07',
    outcome: 'updated',
    reason: '',
    updatedInsightId: 'rate',
  },
]

/** Шаги прогресса при анализе своей новости. */
export const ANALYZE_STEPS = [
  'Проверяем новость и ищем подтверждения',
  'Сопоставляем с профилем компании',
  'Оцениваем влияние и сценарии',
  'Формулируем действия',
]
