import { useEffect, useRef } from 'react'
import { CircleAlert, RotateCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useServiceStatus } from '@/hooks/useServiceStatus'
import { INITIAL_FEED_LIMIT } from '@/shared/constants/insights'
import { useAppDispatch, useAppSelector } from '@/store/hooks/redux'
import { getCompanyProfile } from '@/store/service/Company/getCompanyProfile'
import { getInsightsFeed } from '@/store/service/Insights/getInsightsFeed'

/**
 * Плашка над контентом, когда бэкенд не готов отдавать данные. Появляется
 * и если сервер отключился уже после входа: готовность проверяется раз в
 * минуту и сразу после неудачного фонового обновления ленты. Когда сервис
 * снова доступен, профиль и лента перезагружаются сами — без «Повторить».
 */
const ServiceStatusBanner = () => {
  const dispatch = useAppDispatch()
  const companyId = useAppSelector((state) => state.company.currentCompanyId)
  // Неудачное фоновое обновление ленты — повод проверить сервис сразу.
  const refreshFailedAt = useAppSelector(
    (state) => state.insights.refreshFailedAt
  )
  const { problem, checking, recheck } = useServiceStatus(refreshFailedAt)
  const hadProblem = useRef(false)

  useEffect(() => {
    if (problem) {
      hadProblem.current = true
      return
    }
    if (!hadProblem.current || !companyId) return
    hadProblem.current = false
    dispatch(getCompanyProfile(companyId))
    dispatch(getInsightsFeed({ companyId, limit: INITIAL_FEED_LIMIT }))
  }, [problem, companyId, dispatch])

  if (!problem) return null

  return (
    <div
      role="alert"
      className="flex flex-wrap items-center gap-3 rounded-2xl bg-tone-risk px-4 py-3 text-[15px] text-tone-risk-fg"
    >
      <CircleAlert className="h-5 w-5 shrink-0" />
      <span className="min-w-0 flex-1">{problem}</span>
      <Button
        variant="secondary"
        onClick={recheck}
        disabled={checking}
        className="h-auto bg-white px-3 py-1.5 text-sm font-medium"
      >
        <RotateCw className={checking ? 'animate-spin' : undefined} />
        Проверить снова
      </Button>
    </div>
  )
}

export default ServiceStatusBanner
