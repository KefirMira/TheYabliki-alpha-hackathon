import { FEED_PAGE_SIZE } from '@/shared/constants/insights'
import type {
  ICreatedAnalysis,
  IInsightCard,
  IInsightFeed,
} from '@/store/models/IInsight'

import { apiRequest } from './request'

/** Лента и карточка инсайтов компании (`docs/INSIGHTS_API.md`). */

export interface FetchInsightsFeedParams {
  companyId: string
  limit?: number
  /** Без курсора — первая страница. */
  cursor?: string | null
}

const companyPath = (companyId: string) =>
  `/api/companies/${encodeURIComponent(companyId)}`

export const fetchInsightsFeed = ({
  companyId,
  limit = FEED_PAGE_SIZE,
  cursor,
}: FetchInsightsFeedParams) => {
  const params = new URLSearchParams({ limit: String(limit) })
  if (cursor) params.append('cursor', cursor)

  return apiRequest<IInsightFeed>(
    `${companyPath(companyId)}/insights?${params.toString()}`,
    { method: 'GET' },
    'Не удалось загрузить ленту инсайтов'
  )
}

export const fetchInsight = (companyId: string, insightId: number) =>
  apiRequest<IInsightCard>(
    `${companyPath(companyId)}/insights/${insightId}`,
    { method: 'GET' },
    'Не удалось загрузить инсайт'
  )

/** Анализ через LLM идёт дольше обычного запроса. */
const ANALYSIS_TIMEOUT_MS = 120000

export interface AnalysisNewsInput {
  title?: string
  text: string
}

/**
 * Анализ своей новости: `POST /api/companies/{source_id}/analyses`.
 * Синхронный и не идемпотентный — автоматически не повторяем, иначе второй
 * запуск и второй вызов LLM. В демо-режиме бэкенд отвечает 503
 * AI_DISABLED_IN_DEMO до обращения к AI.
 */
export const createAnalysis = (companyId: string, news: AnalysisNewsInput) =>
  apiRequest<ICreatedAnalysis>(
    `${companyPath(companyId)}/analyses`,
    { method: 'POST', body: JSON.stringify({ news }) },
    'Не удалось проанализировать новость',
    ANALYSIS_TIMEOUT_MS
  )
