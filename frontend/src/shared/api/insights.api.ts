import { FEED_PAGE_SIZE } from '@/shared/constants/insights'
import type { IInsightCard, IInsightFeed } from '@/store/models/IInsight'

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
