import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { FEATURES } from '@/shared/constants/features'
import { DAY_SUMMARY } from '@/shared/mocks/pulse'
import Card from '@/shared/ui/Card'
import { useAppDispatch, useAppSelector } from '@/store/hooks/redux'
import { selectPulseInsights } from '@/store/selectors/pulse'
import { getInsightsFeed } from '@/store/service/Insights/getInsightsFeed'
import {
  FeedMessage,
  FeedSkeleton,
  NoCompanyMessage,
  RetryButton,
} from '@/widgets/Insights/FeedStates'
import InsightCard from '@/widgets/Insights/InsightCard'
import { filterFeed, filtersFromParams } from '@/widgets/Insights/feedFilter'
import FactorPulse from '@/widgets/Summary/FactorPulse'

const MAIN_COUNT = 6

/** Сводка: что важно сегодня — самые важные инсайты компании. */
const PulseSummary = () => {
  const dispatch = useAppDispatch()
  const companyId = useAppSelector((state) => state.company.currentCompanyId)
  const { loadingList, isInitialized, error } = useAppSelector(
    (state) => state.insights
  )
  const insights = useAppSelector(selectPulseInsights)
  // Порядок «по важности», как в ленте по умолчанию.
  const main = filterFeed(
    insights,
    filtersFromParams(new URLSearchParams()),
    []
  ).items.slice(0, MAIN_COUNT)

  const renderMain = () => {
    if (!companyId) return <NoCompanyMessage />
    if (loadingList || !isInitialized) {
      return <FeedSkeleton count={3} className="2xl:grid-cols-3" />
    }
    if (error) {
      return (
        <FeedMessage
          error
          title="Инсайты не загрузились"
          text={error}
          action={
            <RetryButton
              onClick={() =>
                companyId && dispatch(getInsightsFeed({ companyId }))
              }
            />
          }
        />
      )
    }
    if (main.length === 0) {
      return (
        <FeedMessage
          title="Важных событий пока нет"
          text="Пульс покажет здесь события, которые сильнее всего влияют на компанию."
          action={
            <Button asChild variant="secondary" className="mt-1">
              <Link to="/pulse/insights/new">Проанализировать новость</Link>
            </Button>
          }
        />
      )
    }
    return (
      <div className="grid items-stretch gap-4 md:grid-cols-2 2xl:grid-cols-3">
        {main.map((insight) => (
          <InsightCard key={insight.id} insight={insight} />
        ))}
      </div>
    )
  }

  return (
    <>
      {FEATURES.daySummary && (
        <Card>
          <div className="flex items-center justify-between gap-3">
            <span className="text-[17px] font-semibold">Сводка дня</span>
            <span className="text-[13px] text-ink-3">{DAY_SUMMARY.meta}</span>
          </div>
          <p className="max-w-[1120px] text-base leading-6 text-pretty">
            {DAY_SUMMARY.text}
          </p>
        </Card>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-[17px] font-semibold leading-6">Главное сегодня</h2>
        {renderMain()}
      </section>

      {FEATURES.factorPulse && <FactorPulse />}

      {FEATURES.sources && (
        <Link
          to="/pulse/sources"
          className="-ml-3.5 inline-flex items-center gap-2 self-start rounded-xl px-3.5 py-3 text-[15px] font-medium transition-colors hover:bg-surface-chip"
        >
          Смотреть источники
          <ArrowRight className="h-[18px] w-[18px]" />
        </Link>
      )}
    </>
  )
}

export default PulseSummary
