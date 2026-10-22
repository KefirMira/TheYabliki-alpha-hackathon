import { useCallback, useEffect, useState } from 'react'

import { fetchInsight } from '@/shared/api/insights.api'
import { ApiError } from '@/shared/api/request'
import { mapInsightCard } from '@/shared/api/mappers/pulseMappers'
import type { IInsightDetail, IPulseInsight } from '@/store/models/IPulse'

interface InsightCardState {
  data: { insight: IPulseInsight; detail: IInsightDetail } | null
  loading: boolean
  error: string | null
}

/**
 * Карточка инсайта из API. В стор не кладём: карточка нужна только своей
 * странице. Ответ на устаревший запрос (сменили инсайт или компанию) не
 * применяется.
 */
export const useInsightCard = (companyId: string | null, insightId: string) => {
  const [state, setState] = useState<InsightCardState>({
    data: null,
    loading: true,
    error: null,
  })
  const [attempt, setAttempt] = useState(0)
  const numericId = Number(insightId)
  const validId = Number.isInteger(numericId) && numericId > 0

  useEffect(() => {
    if (!companyId || !validId) {
      setState({ data: null, loading: false, error: null })
      return
    }
    let stale = false
    setState({ data: null, loading: true, error: null })
    fetchInsight(companyId, numericId)
      .then((card) => {
        if (!stale) {
          setState({ data: mapInsightCard(card), loading: false, error: null })
        }
      })
      .catch((error: Error) => {
        if (stale) return
        // Чужой или удалённый инсайт — «не найден», а не сбой загрузки.
        const notFound =
          error instanceof ApiError && error.code === 'INSIGHT_NOT_FOUND'
        setState({
          data: null,
          loading: false,
          error: notFound ? null : error.message,
        })
      })
    return () => {
      stale = true
    }
  }, [companyId, numericId, validId, attempt])

  const reload = useCallback(() => setAttempt((current) => current + 1), [])

  return { ...state, reload }
}
