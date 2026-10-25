/**
 * Модели экранов «Пульса бизнеса». Ответы API приводятся к ним в
 * `@/shared/api/mappers/pulseMappers`. Только то, что приходит из API:
 * блок без данных не показывается, значения не выдумываются.
 */

/** Тип инсайта из API: риск, возможность, «риск и возможность», информация. */
export type PulseKind = 'risk' | 'opp' | 'mixed' | 'info'

/** Релевантность словами — так её отдаёт API. */
export type RelevanceLevel = 'high' | 'medium' | 'low'

/** Инсайт в ленте, сводке, виджете на главной и колокольчике. */
export interface IPulseInsight {
  id: string
  kind: PulseKind
  /** Релевантность словами (API); unknown не показываем. */
  relevanceLevel?: RelevanceLevel
  title: string
  /** Вывод анализа одной строкой — на странице инсайта. */
  meaning?: string
  /** «Анализ от 3 января 2026» или «Новое · Анализ от …». */
  updated: string
  /** Пришёл при фоновом обновлении и ещё не открыт. */
  isNew?: boolean
  /** Возраст в часах — для сортировки «по времени». */
  ageHours: number
}

/** Позиция Альфа-Банка — точный фрагмент аналитики банка из PDF. */
export interface IBankPosition {
  author: string
  date: string
  quote: string
  document: string
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

/** Фрагмент-доказательство: точный текст из источника, не пересказ. */
export interface IInsightEvidence {
  text: string
  document: string | null
  page: number | null
}

/** Содержимое страницы инсайта. Пустой список — блока нет на странице. */
export interface IInsightDetail {
  fact: string
  synthetic?: boolean
  savedPilot?: {
    model: string
    pilotDate: string
    importedAt: string
    duration: number
    usage: {
      prompt_tokens: number
      completion_tokens: number
      reasoning_tokens: number
      total_tokens: number
    }
    artifactSha256: string
    events: { tool: string; reason: string }[]
  }
  impact: string
  /** null — у банка нет опубликованной позиции по теме. */
  bank: IBankPosition | null
  risks: string[]
  opportunities: string[]
  /** Рекомендации анализа. */
  actions: string[]
  sources: IInsightSource[]
  evidence: IInsightEvidence[]
  /** Итог проверки достоверности; пусто — проверки нет. */
  confidence: string
  financialReview?: {
    status: string
    findings: {
      code: string
      disposition: string
      claim: string
      explanation: string
    }[]
  }
  /** Замечания проверки достоверности (validation.warnings). */
  warnings: string[]
  logTime: string
  log: IAnalysisStep[]
}
