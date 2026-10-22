import { ArrowRight, ArrowUpDown, Bookmark, Loader2, Plus } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { FEATURES } from '@/shared/constants/features'
import Segmented from '@/shared/ui/Segmented'
import { useAppDispatch, useAppSelector } from '@/store/hooks/redux'
import type { PulseKind } from '@/store/models/IPulse'
import { toggleFavorite } from '@/store/reducers/PulseSlice'
import { selectPulseInsights } from '@/store/selectors/pulse'
import { getInsightsFeed } from '@/store/service/Insights/getInsightsFeed'
import {
  FeedMessage,
  FeedSkeleton,
  NoCompanyMessage,
  RetryButton,
} from '@/widgets/Insights/FeedStates'
import InsightCard from '@/widgets/Insights/InsightCard'
import {
  type FeedType,
  filterFeed,
  filtersFromParams,
} from '@/widgets/Insights/feedFilter'

const TYPE_LABELS: Record<FeedType, string> = {
  all: 'Все',
  risk: 'Риски',
  opp: 'Возможности',
  hyp: 'Гипотезы',
  mixed: 'Риск и возможность',
  info: 'Информация',
}

/** Вкладки макета всегда; остальные типы — только если они пришли из API. */
const ALWAYS_SHOWN: FeedType[] = ['all', 'risk', 'opp']
const OPTIONAL: PulseKind[] = ['hyp', 'mixed', 'info']

/** Лента инсайтов компании из API. */
const Insights = () => {
  const dispatch = useAppDispatch()
  const [params, setParams] = useSearchParams()
  const companyId = useAppSelector((state) => state.company.currentCompanyId)
  const favorites = useAppSelector((state) => state.pulse.favorites)
  const {
    loadingList,
    loadingMore,
    isInitialized,
    error,
    errorMore,
    nextCursor,
  } = useAppSelector((state) => state.insights)
  const insights = useAppSelector(selectPulseInsights)

  const filters = filtersFromParams(params)
  const { items, counts } = filterFeed(insights, filters, favorites)
  const tabs = [...ALWAYS_SHOWN, ...OPTIONAL.filter((kind) => counts[kind] > 0)]

  // Пустое значение — фильтр по умолчанию, из адреса его убираем.
  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const reload = () => {
    if (companyId) dispatch(getInsightsFeed({ companyId }))
  }

  const loadMore = () => {
    if (companyId && nextCursor) {
      dispatch(getInsightsFeed({ companyId, cursor: nextCursor }))
    }
  }

  const renderFeed = () => {
    if (!companyId) return <NoCompanyMessage />
    if (loadingList || !isInitialized) return <FeedSkeleton />
    if (error) {
      return (
        <FeedMessage
          error
          title="Лента не загрузилась"
          text={error}
          action={<RetryButton onClick={reload} />}
        />
      )
    }
    if (insights.length === 0) {
      return (
        <FeedMessage
          title="Инсайтов пока нет"
          text="Когда Пульс найдёт события, которые влияют на компанию, они появятся здесь. Можно проанализировать свою новость."
        />
      )
    }
    if (items.length === 0) {
      return (
        <FeedMessage
          title="Нет инсайтов по выбранным фильтрам"
          text="Попробуйте убрать часть фильтров."
          action={
            <Button
              variant="secondary"
              onClick={() => setParams({}, { replace: true })}
              className="mt-1"
            >
              Сбросить фильтры
            </Button>
          }
        />
      )
    }
    return (
      <div className="grid auto-rows-fr gap-4 md:grid-cols-2">
        {items.map((insight) => (
          <InsightCard
            key={insight.id}
            insight={insight}
            favorite={favorites.includes(insight.id)}
            onToggleFavorite={(id) => dispatch(toggleFavorite(id))}
          />
        ))}
      </div>
    )
  }

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <Segmented
          label="Тип инсайтов"
          className="scroll-x-quiet"
          value={filters.type}
          onChange={(type) => setParam('type', type === 'all' ? null : type)}
          options={tabs.map((type) => ({
            value: type,
            label: TYPE_LABELS[type],
            count: counts[type],
          }))}
        />
        <Button asChild className="h-auto px-3.5 py-[9px] text-sm">
          <Link to="/pulse/insights/new">
            <Plus />
            Проанализировать новость
          </Link>
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setParam('fav', filters.favoritesOnly ? null : '1')}
          aria-pressed={filters.favoritesOnly}
          className={cn(
            'inline-flex items-center gap-1.5 rounded-[10px] px-3 py-[7px] text-[13px] font-medium transition-colors',
            filters.favoritesOnly ? 'bg-ink text-white' : 'bg-surface-chip'
          )}
        >
          <Bookmark
            className="h-3.5 w-3.5"
            fill={filters.favoritesOnly ? 'currentColor' : 'none'}
          />
          Избранное
          <span className="text-xs font-semibold opacity-70">
            {favorites.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() =>
            setParam('sort', filters.sort === 'time' ? null : 'time')
          }
          className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-[10px] px-2.5 py-[7px] text-[13px] font-medium transition-colors hover:bg-surface-chip"
        >
          <ArrowUpDown className="h-3.5 w-3.5" />
          {filters.sort === 'time' ? 'По времени' : 'По важности'}
        </button>
      </div>

      {companyId && isInitialized && !error && (
        <p className="text-sm text-ink-2">
          Найдено: <b>{items.length}</b>
          {nextCursor && ' · показаны загруженные'}
        </p>
      )}

      {renderFeed()}

      {nextCursor && !loadingList && (
        <div className="flex flex-col items-center gap-2">
          {errorMore && (
            <p className="text-sm text-tone-risk-fg" role="alert">
              {errorMore}
            </p>
          )}
          <Button variant="secondary" onClick={loadMore} disabled={loadingMore}>
            {loadingMore && <Loader2 className="animate-spin" />}
            {errorMore ? 'Повторить' : 'Показать ещё'}
          </Button>
        </div>
      )}

      {FEATURES.history && (
        <Link
          to="/pulse/insights/history"
          className="inline-flex items-center gap-2 self-start rounded-xl px-3.5 py-3 text-[15px] font-medium transition-colors hover:bg-surface-chip"
        >
          История инсайтов
          <ArrowRight className="h-[18px] w-[18px]" />
        </Link>
      )}
    </>
  )
}

export default Insights
