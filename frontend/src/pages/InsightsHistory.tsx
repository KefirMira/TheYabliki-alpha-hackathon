import { useState } from 'react'
import {
  ArrowLeft,
  Check,
  ChevronRight,
  Circle,
  type LucideIcon,
  RefreshCw,
  Timer,
  X,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { cn } from '@/lib/utils'
import { HISTORY_ROWS, PULSE_INSIGHTS } from '@/shared/mocks/pulse'
import Segmented from '@/shared/ui/Segmented'
import { plural } from '@/shared/utils/plural'
import type { HistoryOutcome } from '@/store/models/IPulse'
import InsightKindTag from '@/widgets/Insights/InsightKindTag'

interface OutcomeMeta {
  label: string
  icon: LucideIcon
  className: string
}

/** Итог инсайта: исход гипотезы → обновление → истёк срок. */
const OUTCOMES: Record<HistoryOutcome, OutcomeMeta> = {
  confirmed: {
    label: 'Подтвердилась',
    icon: Check,
    className: 'bg-tone-opp text-tone-opp-fg',
  },
  refuted: {
    label: 'Не подтвердилась',
    icon: X,
    className: 'bg-line-soft text-ink-3',
  },
  unchecked: {
    label: 'Не проверена',
    icon: Circle,
    className: 'border border-dashed border-ink-4 text-ink-3',
  },
  updated: {
    label: 'Есть обновление',
    icon: RefreshCw,
    className: 'bg-tone-info text-tone-info-fg',
  },
  expired: {
    label: 'Истёк срок',
    icon: Timer,
    className: 'bg-surface-page text-ink-2',
  },
}

type OutcomeFilter = 'all' | HistoryOutcome

const FILTERS: OutcomeFilter[] = [
  'all',
  'confirmed',
  'refuted',
  'unchecked',
  'updated',
  'expired',
]

const GRID =
  'grid grid-cols-[72px_180px_minmax(0,1fr)_220px_24px] items-center gap-4'

/** История: устаревшие инсайты и проверка гипотез задним числом. */
const InsightsHistory = () => {
  const [filter, setFilter] = useState<OutcomeFilter>('all')
  const rows = HISTORY_ROWS.filter(
    (row) => filter === 'all' || row.outcome === filter
  )

  return (
    <>
      <div className="flex items-end justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          <Link
            to="/pulse/insights"
            className="inline-flex items-center gap-1.5 self-start text-sm font-medium text-ink-2 hover:text-ink"
          >
            <ArrowLeft className="h-4 w-4" />
            Лента инсайтов
          </Link>
          <h1 className="text-2xl font-bold leading-[1.2]">История инсайтов</h1>
        </div>
        <span className="text-sm text-ink-3">
          {plural(rows.length, ['инсайт', 'инсайта', 'инсайтов'])}
        </span>
      </div>

      <Segmented
        label="Итог инсайта"
        className="scroll-x-quiet self-start"
        value={filter}
        onChange={setFilter}
        options={FILTERS.map((value) => ({
          value,
          label: value === 'all' ? 'Все' : OUTCOMES[value].label,
          count:
            value === 'all'
              ? HISTORY_ROWS.length
              : HISTORY_ROWS.filter((row) => row.outcome === value).length,
        }))}
      />

      <div className="overflow-x-auto rounded-3xl bg-white px-5 py-2">
        <div className="min-w-[860px]">
          <div
            className={cn(
              GRID,
              'py-3 text-xs font-semibold tracking-[0.06em] text-ink-3'
            )}
          >
            <span>ДАТА</span>
            <span>ТИП</span>
            <span>ИНСАЙТ</span>
            <span>ИТОГ</span>
            <span />
          </div>

          {rows.map((row) => {
            const insight = PULSE_INSIGHTS[row.insightId]
            const outcome = OUTCOMES[row.outcome]
            const Icon = outcome.icon
            return (
              <Link
                key={row.insightId}
                to={`/pulse/insights/${row.insightId}`}
                className={cn(
                  GRID,
                  '-mx-3 rounded-xl border-t border-line-soft px-3 py-3.5 transition-colors hover:bg-surface-page'
                )}
              >
                <span className="text-sm tabular-nums text-ink-2">
                  {row.date}
                </span>
                <span>
                  <InsightKindTag insight={insight} withIcon={false} />
                </span>
                <span className="flex min-w-0 flex-col gap-0.5">
                  <span className="text-[15px] font-semibold leading-[21px]">
                    {insight.title}
                  </span>
                  <span className="truncate text-[13px] text-ink-3">
                    {insight.meaning}
                  </span>
                </span>
                <span className="flex min-w-0 flex-col items-start gap-1">
                  <span
                    className={cn(
                      'inline-flex items-center gap-[5px] whitespace-nowrap rounded-md py-[3px] pl-1.5 pr-2 text-xs font-semibold',
                      outcome.className
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {outcome.label}
                  </span>
                  {row.reason && (
                    <span className="truncate text-xs text-ink-3">
                      {row.reason}
                    </span>
                  )}
                </span>
                <ChevronRight className="h-4 w-4 justify-self-end text-ink-4" />
              </Link>
            )
          })}
        </div>
      </div>
    </>
  )
}

export default InsightsHistory
