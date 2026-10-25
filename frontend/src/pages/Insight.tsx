import { useEffect } from 'react'
import { Bookmark, X } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { useFavorites } from '@/hooks/useFavorites'
import { useInsightCard } from '@/hooks/useInsightCard'
import BackLink from '@/shared/ui/BackLink'
import Card from '@/shared/ui/Card'
import LayerTag from '@/shared/ui/LayerTag'
import { useAppDispatch, useAppSelector } from '@/store/hooks/redux'
import { markInsightSeen } from '@/store/reducers/InsightsSlice'
import InsightSidePanel from '@/widgets/Insight/InsightSidePanel'
import {
  Actions,
  BankPosition,
  Evidence,
  RisksOpportunities,
  Sources,
  WhatHappened,
  WhatItMeans,
  FinancialReviewSection,
} from '@/widgets/Insight/InsightSections'
import InsightKindTag from '@/widgets/Insights/InsightKindTag'
import {
  FeedMessage,
  NoCompanyMessage,
  RetryButton,
} from '@/widgets/Insights/FeedStates'
import { relevanceText } from '@/widgets/Insights/insightView'

const InsightSkeleton = () => (
  <div className="grid items-start gap-4 2xl:grid-cols-[minmax(0,1fr)_400px]">
    <div className="flex flex-col gap-4">
      <div className="h-[220px] animate-pulse rounded-3xl bg-white" />
      <div className="grid gap-4 md:grid-cols-2">
        <div className="h-[180px] animate-pulse rounded-3xl bg-white" />
        <div className="h-[180px] animate-pulse rounded-3xl bg-white" />
      </div>
    </div>
    <div className="h-[320px] animate-pulse rounded-3xl bg-white" />
  </div>
)

/**
 * Страница инсайта из API. Блоки без данных не показываются; позиция банка
 * обязательна — если её нет, это говорится явно.
 */
const Insight = () => {
  const { insightId = '' } = useParams()
  const navigate = useNavigate()
  const dispatch = useAppDispatch()
  const { favorites, toggle, hide } = useFavorites()
  const companyId = useAppSelector((state) => state.company.currentCompanyId)
  const { data, loading, error, reload } = useInsightCard(companyId, insightId)
  const openedId = data?.insight.id

  // Открытый инсайт больше не «новый» в ленте.
  useEffect(() => {
    if (openedId) dispatch(markInsightSeen(Number(openedId)))
  }, [openedId, dispatch])

  const back = <BackLink to="/pulse/insights">Все инсайты</BackLink>

  if (!companyId) {
    return (
      <>
        {back}
        <NoCompanyMessage />
      </>
    )
  }

  if (loading) {
    return (
      <>
        {back}
        <InsightSkeleton />
      </>
    )
  }

  if (error) {
    return (
      <>
        {back}
        <FeedMessage
          error
          title="Инсайт не загрузился"
          text={error}
          action={<RetryButton onClick={reload} />}
        />
      </>
    )
  }

  if (!data) {
    return (
      <>
        {back}
        <Card className="items-center py-12 text-center">
          <span className="text-lg font-semibold">Инсайт не найден</span>
          <span className="text-[15px] text-ink-2">
            Возможно, он относится к другой компании.
          </span>
        </Card>
      </>
    )
  }

  const { insight, detail } = data
  const isFavorite = favorites.includes(insight.id)
  const relevance = relevanceText(insight)

  const handleNotRelevant = () => {
    hide(insight.id)
    navigate('/pulse/insights')
  }

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4">
        {back}
        <div className="flex gap-2">
          <Button
            variant="secondary"
            onClick={() => toggle(insight.id)}
            aria-pressed={isFavorite}
            className="h-auto px-3.5 py-[9px] text-sm font-medium"
          >
            <Bookmark
              className={isFavorite ? 'text-brand' : undefined}
              fill={isFavorite ? 'currentColor' : 'none'}
            />
            {isFavorite ? 'В избранном' : 'В избранное'}
          </Button>
          <Button
            variant="secondary"
            onClick={handleNotRelevant}
            className="h-auto px-3.5 py-[9px] text-sm font-medium"
          >
            <X />
            Не относится к нам
          </Button>
        </div>
      </div>

      <div className="grid items-start gap-4 2xl:grid-cols-[minmax(0,1fr)_400px]">
        <div className="flex min-w-0 flex-col gap-4">
          <Card className="gap-3.5 p-5 md:p-7">
            <div className="flex items-center justify-between gap-2">
              <InsightKindTag insight={insight} withIcon={false} />
              {relevance && (
                <span className="text-sm font-semibold text-ink-2">
                  {relevance}
                </span>
              )}
            </div>
            <h1 className="max-w-[900px] text-[30px] font-bold leading-[1.2] text-pretty">
              {insight.title}
            </h1>
            {insight.meaning && (
              <p className="text-[17px] leading-[26px] text-ink-2 text-pretty">
                {insight.meaning}
              </p>
            )}
            <span className="self-end text-[13px] text-ink-3">
              {insight.updated}
            </span>
          </Card>

          <div className="flex flex-wrap items-center gap-2 px-1">
            <span className="mr-1 text-[13px] text-ink-3">
              Как читать инсайт
            </span>
            <LayerTag layer="fact" />
            <LayerTag layer="bank" />
            <LayerTag layer="ai" />
          </div>

          <div className="grid items-stretch gap-4 md:grid-cols-2">
            <WhatHappened detail={detail} />
            {detail.impact && <WhatItMeans detail={detail} />}
            <BankPosition bank={detail.bank} />
            {(detail.risks.length > 0 || detail.opportunities.length > 0) && (
              <RisksOpportunities detail={detail} />
            )}
            {detail.actions.length > 0 && <Actions detail={detail} />}
            <Sources detail={detail} />
            <FinancialReviewSection detail={detail} />
            {detail.evidence.length > 0 && <Evidence detail={detail} />}
          </div>
        </div>

        <InsightSidePanel key={insight.id} detail={detail} />
      </div>
    </>
  )
}

export default Insight
