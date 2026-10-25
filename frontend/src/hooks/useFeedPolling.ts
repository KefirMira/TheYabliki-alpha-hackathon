import { useEffect } from 'react'

import { FEED_POLL_MS } from '@/shared/constants/insights'
import { useAppDispatch, useAppSelector } from '@/store/hooks/redux'
import { refreshInsightsFeed } from '@/store/service/Insights/refreshInsightsFeed'

/**
 * Живая лента: раз в минуту, пока вкладка видна, сверяемся с сервером и
 * дописываем новые инсайты. Скрытая вкладка не опрашивает; вернувшись на
 * неё, обновляемся сразу, если с прошлой сверки прошло больше интервала.
 * Неудачная сверка не останавливает опрос.
 */
export const useFeedPolling = () => {
  const dispatch = useAppDispatch()
  const companyId = useAppSelector((state) => state.company.currentCompanyId)

  useEffect(() => {
    if (!companyId) return

    // Ленту только что загрузил usePulseData — отсчёт от смены компании.
    let lastCheck = Date.now()
    const refresh = () => {
      lastCheck = Date.now()
      dispatch(refreshInsightsFeed({ companyId }))
    }
    const visible = () => document.visibilityState === 'visible'

    const timer = window.setInterval(() => {
      if (visible()) refresh()
    }, FEED_POLL_MS)
    const onVisibilityChange = () => {
      if (visible() && Date.now() - lastCheck >= FEED_POLL_MS) refresh()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)

    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [companyId, dispatch])
}
