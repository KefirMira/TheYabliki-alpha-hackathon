import { type ReactNode, useEffect } from 'react'
import { AlertCircle, Inbox, Loader2, RotateCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useAppDispatch, useAppSelector } from '@/store/hooks/redux'
import { getInsightsFeed } from '@/store/service/Insights/getInsightsFeed'

import InsightFeedCard from './InsightFeedCard'

const SKELETON_CARDS = 4

const FeedSkeleton = () => (
  <div className="grid grid-cols-1 gap-4 md:grid-cols-2" aria-busy="true">
    {Array.from({ length: SKELETON_CARDS }, (_, index) => (
      <div key={index} className="space-y-3 rounded-lg bg-card p-5">
        <Skeleton className="h-6 w-28" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-3 w-40" />
      </div>
    ))}
  </div>
)

const FeedMessage = ({
  icon: Icon,
  title,
  text,
  action,
}: {
  icon: typeof Inbox
  title: string
  text: string
  action?: ReactNode
}) => (
  <div className="flex flex-col items-center gap-3 rounded-lg bg-card px-6 py-14 text-center">
    <Icon className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
    <div className="space-y-1">
      <p className="font-semibold">{title}</p>
      <p className="max-w-md text-sm text-muted-foreground">{text}</p>
    </div>
    {action}
  </div>
)

/** Лента инсайтов текущей компании: первая страница и догрузка по курсору. */
const InsightsFeed = () => {
  const dispatch = useAppDispatch()
  const companyId = useAppSelector((state) => state.company.currentCompanyId)
  const {
    items,
    nextCursor,
    loadingList,
    loadingMore,
    error,
    errorMore,
    isInitialized,
  } = useAppSelector((state) => state.insights)

  useEffect(() => {
    if (companyId) dispatch(getInsightsFeed({ companyId }))
  }, [companyId, dispatch])

  const reload = () => {
    if (companyId) dispatch(getInsightsFeed({ companyId }))
  }

  const loadMore = () => {
    if (companyId && nextCursor) {
      dispatch(getInsightsFeed({ companyId, cursor: nextCursor }))
    }
  }

  if (!companyId) {
    return (
      <FeedMessage
        icon={AlertCircle}
        title="Компания не выбрана"
        text="Укажите VITE_DEMO_COMPANY_IDS в .env, пока нет входа по логину."
      />
    )
  }

  if (loadingList || !isInitialized) return <FeedSkeleton />

  if (error) {
    return (
      <FeedMessage
        icon={AlertCircle}
        title="Лента не загрузилась"
        text={error}
        action={
          <Button variant="secondary" onClick={reload}>
            <RotateCw />
            Повторить
          </Button>
        }
      />
    )
  }

  if (items.length === 0) {
    return (
      <FeedMessage
        icon={Inbox}
        title="Инсайтов пока нет"
        text="Когда Пульс найдёт события, которые влияют на компанию, они появятся здесь."
      />
    )
  }

  return (
    <div className="space-y-4">
      <div className="grid auto-rows-fr grid-cols-1 gap-4 md:grid-cols-2">
        {items.map((insight) => (
          <InsightFeedCard key={insight.insight_id} insight={insight} />
        ))}
      </div>

      <div className="flex flex-col items-center gap-2 pt-2">
        {errorMore && (
          <p className="text-sm text-destructive" role="alert">
            {errorMore}
          </p>
        )}
        {nextCursor ? (
          <Button variant="secondary" onClick={loadMore} disabled={loadingMore}>
            {loadingMore && <Loader2 className="animate-spin" />}
            {errorMore ? 'Повторить' : 'Показать ещё'}
          </Button>
        ) : (
          <p className="text-xs text-muted-foreground">
            Показаны все инсайты · {items.length}
          </p>
        )}
      </div>
    </div>
  )
}

export default InsightsFeed
