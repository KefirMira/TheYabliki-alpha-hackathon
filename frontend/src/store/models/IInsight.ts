/**
 * Инсайт — вывод о влиянии новости на компанию (`docs/INSIGHTS_API.md`).
 *
 * `created_at` — время анализа, а не публикации новости. `status` — статус
 * запуска анализа, а не подтверждение прогноза: в ленту попадают только
 * завершённые (COMPLETED).
 */

export type InsightType = 'risk' | 'opportunity' | 'mixed' | 'information'

export type InsightRelevance = 'high' | 'medium' | 'low' | 'unknown'

/** Строка ленты: `GET /api/companies/{source_id}/insights`. */
export interface IInsightFeedItem {
  insight_id: number
  run_id: number
  company_id: string
  /** null — бэкенд тип не определил; из рисков/возможностей не выводим. */
  type: InsightType | null
  relevance: InsightRelevance | null
  summary: string | null
  created_at: string
  status: 'COMPLETED'
}

export interface IInsightFeed {
  items: IInsightFeedItem[]
  /** Токен следующей страницы; передаётся обратно без изменений. */
  next_cursor: string | null
}

export interface IInsightNews {
  id: number
  title: string
  text: string | null
}

export interface IInsightEvidence {
  /** Ключ строки БД — не то же самое, что `id` в sources. */
  id: number
  evidence_type: string
  text: string
  document: string | null
  page: number | null
  chunk_id: number | null
  document_date: string | null
}

/** Источник в том виде, как его сохранил анализ (точность даты сохранена). */
export interface IInsightSource {
  id: number
  document?: string
  page?: number
  chunk_id?: number
  date?: string
  /** TF-IDF-оценка поиска, не уверенность вывода. */
  score?: number
  [key: string]: unknown
}

/** Карточка: `GET /api/companies/{source_id}/insights/{insight_id}`. */
export interface IInsightCard extends IInsightFeedItem {
  news: IInsightNews
  risks: string[]
  opportunities: string[]
  recommendations: string[]
  validation: { passed?: boolean; warnings?: string[]; [key: string]: unknown }
  sources: IInsightSource[]
  evidence: IInsightEvidence[]
}

/** Ответ анализа новости: `POST /api/companies/{source_id}/news/{news_id}/analyses`. */
export interface ICreatedAnalysis {
  run_id: number
  insight_id: number
  news_id: number
  status: 'COMPLETED'
  company_id: string
  analysis: {
    company_id: string
    news: string
    relevance: InsightRelevance | null
    summary: string | null
    risks: string[]
    opportunities: string[]
    recommendations: string[]
    sources: IInsightSource[]
    validation: { passed?: boolean; warnings?: string[] }
  }
}
