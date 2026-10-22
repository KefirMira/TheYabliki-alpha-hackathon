import { useEffect } from 'react'

import { INITIAL_FEED_LIMIT } from '@/shared/constants/insights'
import { useAppDispatch, useAppSelector } from '@/store/hooks/redux'
import { getCompanyProfile } from '@/store/service/Company/getCompanyProfile'
import { getInsightsFeed } from '@/store/service/Insights/getInsightsFeed'

/**
 * Данные компании для всего интернет-банка: профиль и лента инсайтов. Один
 * запрос на смену компании — экраны читают общий стор.
 */
export const usePulseData = () => {
  const dispatch = useAppDispatch()
  const companyId = useAppSelector((state) => state.company.currentCompanyId)

  useEffect(() => {
    if (!companyId) return
    dispatch(getCompanyProfile(companyId))
    dispatch(getInsightsFeed({ companyId, limit: INITIAL_FEED_LIMIT }))
  }, [companyId, dispatch])
}
