/**
 * Модели экранов «Пульса бизнеса» — контракт вёрстки. Ответы API приводятся
 * к ним в `@/shared/api/mappers/pulseMappers`. Поля, которых в API пока нет,
 * необязательны: блок без данных не показывается, значения не выдумываются.
 */

/**
 * Тип инсайта. mixed и info приходят из API («риск и возможность»,
 * «информация»); hyp — гипотеза, в API пока не выделяется.
 */
export type PulseKind = 'risk' | 'opp' | 'hyp' | 'mixed' | 'info'

/** Релевантность словами — так её отдаёт API. */
export type RelevanceLevel = 'high' | 'medium' | 'low'

/** Уровень влияния: 1 — низкое, 2 — среднее, 3 — высокое. */
export type ImpactLevel = 1 | 2 | 3

export type DataStrength = 'низкая' | 'средняя' | 'высокая'

/** Фактор, через который событие влияет на компанию. */
export type PulseFactor = 'rate' | 'fuel' | 'cp' | 'dem' | 'reg' | 'fx'

/** Горизонт влияния. */
export type PulseHorizon = 'now' | 'm3' | 'm12'

/** Инсайт в ленте, сводке и виджете на главной. */
export interface IPulseInsight {
  id: string
  kind: PulseKind
  /** Уровень влияния; в API пока нет. */
  level?: ImpactLevel
  /** Релевантность для компании, %. У гипотез вместо неё — сила данных. */
  relevance?: number
  /** Релевантность словами (API); unknown не показываем. */
  relevanceLevel?: RelevanceLevel
  strength?: DataStrength
  factor?: PulseFactor
  horizon?: PulseHorizon
  title: string
  /** «Что это значит для вас» — одна строка. */
  meaning?: string
  /** Гипотеза: что подтверждает и что не подтверждает. */
  pro?: string
  con?: string
  /** Признаки компании, по которым событие отобрано («почему вам»). */
  chips: string[]
  /** «Обновлён 2 ч назад», «Анализ от 3 января» или «Новое · 5 мин назад». */
  updated: string
  isNew?: boolean
  /** Возраст в часах — для сортировки «по времени». */
  ageHours: number
}

export interface IBankPosition {
  author: string
  date: string
  quote: string
  /** Пересмотр прогноза банка: было → стало. */
  change?: { label: string; previous: string; current: string }
  document: string
}

export type ScenarioLikelihood = 'Вероятно' | 'Возможно' | 'Маловероятно'

export interface IInsightScenario {
  likelihood: ScenarioLikelihood
  text: string
  strength: DataStrength
  basis: string
}

export interface IInsightAction {
  title: string
  description: string
  /** Предложение продукта банка — показывается с дисклеймером. */
  offer?: boolean
  cta?: string
}

export interface IInsightAffected {
  name: string
  description: string
  level: ImpactLevel
}

export interface IInsightSource {
  name: string
  description: string
}

export interface IAnalysisStep {
  title: string
  description: string
  /** Шаг с замечанием (например, проверка не пройдена). */
  warning?: boolean
}

export interface IInsightQuestion {
  question: string
  answer: string
}

/** Фрагмент-доказательство: точный текст из источника, не пересказ. */
export interface IInsightEvidence {
  text: string
  document: string | null
  page: number | null
}

/**
 * Содержимое страницы инсайта. Пустой список — блока нет на странице:
 * данных для него в API пока нет, выдумывать их нельзя.
 */
export interface IInsightDetail {
  fact: string
  impact: string
  figures: { value: string; label: string }[]
  /** null — у банка нет опубликованной позиции по теме. */
  bank: IBankPosition | null
  affected: IInsightAffected[]
  /** Риски и возможности списком (API). */
  risks: string[]
  opportunities: string[]
  actions: IInsightAction[]
  scenarios: IInsightScenario[]
  sources: IInsightSource[]
  evidence: IInsightEvidence[]
  /** Итог проверки достоверности; пусто — проверки нет. */
  confidence: string
  /** Замечания проверки достоверности (validation.warnings). */
  warnings: string[]
  logTime: string
  log: IAnalysisStep[]
  questions: IInsightQuestion[]
}

/** Итог инсайта в истории. */
export type HistoryOutcome =
  'confirmed' | 'refuted' | 'unchecked' | 'updated' | 'expired'

export interface IHistoryRow {
  insightId: string
  date: string
  outcome: HistoryOutcome
  /** Основание итога: «ЦБ сохранил ставку 14% 11.09». */
  reason: string
  /** Для «Есть обновление» — новый инсайт по той же теме. */
  updatedInsightId?: string
}

export type SourceType = 'bank' | 'stat' | 'reg' | 'mkt' | 'media'

export interface INewsSource {
  name: string
  description: string
  type: SourceType
  /** Материалов за сутки — для сортировки «по числу материалов». */
  materials: number
  updated: string
}
