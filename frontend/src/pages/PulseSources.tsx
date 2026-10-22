import { useState } from 'react'
import { ArrowUpDown, ArrowUpRight } from 'lucide-react'

import { cn } from '@/lib/utils'
import { NEWS_SOURCES, SOURCE_STATS } from '@/shared/mocks/pulse'
import BackLink from '@/shared/ui/BackLink'
import Card from '@/shared/ui/Card'
import Segmented from '@/shared/ui/Segmented'
import type { INewsSource, SourceType } from '@/store/models/IPulse'

const TYPE_META: Record<SourceType, { label: string; className: string }> = {
  bank: {
    label: 'Аналитика Альфа-Банка',
    className: 'bg-tone-info text-tone-info-fg',
  },
  stat: { label: 'Статистика', className: 'bg-line-soft text-ink-2' },
  reg: { label: 'Регулятор', className: 'bg-tone-hyp text-tone-hyp-fg' },
  mkt: { label: 'Биржа', className: 'bg-tone-opp text-tone-opp-fg' },
  media: { label: 'СМИ', className: 'bg-surface-page text-ink-2' },
}

const TABS: { value: 'all' | SourceType; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'bank', label: 'Аналитика банка' },
  { value: 'stat', label: 'Статистика' },
  { value: 'reg', label: 'Регулятор' },
  { value: 'mkt', label: 'Биржа' },
  { value: 'media', label: 'СМИ' },
]

type SortMode = 'fresh' | 'name' | 'count'

const SORT_LABELS: Record<SortMode, string> = {
  fresh: 'Сначала свежие',
  name: 'По алфавиту',
  count: 'По числу материалов',
}

const NEXT_SORT: Record<SortMode, SortMode> = {
  fresh: 'name',
  name: 'count',
  count: 'fresh',
}

/** «5 мин назад» → минуты, чтобы сортировать по свежести. */
const minutesAgo = (updated: string) => {
  const match = /(\d+)\s*(мин|ч|д)/.exec(updated)
  if (!match) return Number.MAX_SAFE_INTEGER
  const unit = { мин: 1, ч: 60, д: 1440 }[match[2] as 'мин' | 'ч' | 'д']
  return Number(match[1]) * unit
}

const sorters: Record<SortMode, (a: INewsSource, b: INewsSource) => number> = {
  fresh: (a, b) => minutesAgo(a.updated) - minutesAgo(b.updated),
  name: (a, b) => a.name.localeCompare(b.name, 'ru'),
  count: (a, b) => b.materials - a.materials,
}

/** Источники: что и откуда собирает Пульс — качество сбора на виду. */
const PulseSources = () => {
  const [type, setType] = useState<'all' | SourceType>('all')
  const [sort, setSort] = useState<SortMode>('fresh')

  const sources = NEWS_SOURCES.filter(
    (source) => type === 'all' || source.type === type
  ).sort(sorters[sort])

  return (
    <>
      <BackLink to="/pulse/summary">Сводка</BackLink>

      <Card>
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold leading-[1.2]">Источники</h1>
          <p className="max-w-[820px] text-[15px] text-ink-2 text-pretty">
            Пульс собирает материалы из аналитики Альфа-Банка, официальной
            статистики и СМИ, удаляет дубли и не использует в выводах материалы
            старше 12 месяцев.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {SOURCE_STATS.map((stat) => (
            <div
              key={stat.label}
              className="flex flex-col gap-1 rounded-2xl bg-surface-page p-4"
            >
              <span className="text-[28px] font-bold tracking-[-0.01em]">
                {stat.value}
              </span>
              <span className="text-sm text-ink-2">{stat.label}</span>
            </div>
          ))}
        </div>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-4">
        <Segmented
          size="sm"
          label="Тип источника"
          className="scroll-x-quiet"
          value={type}
          onChange={setType}
          options={TABS.map((tab) => ({
            ...tab,
            count:
              tab.value === 'all'
                ? NEWS_SOURCES.length
                : NEWS_SOURCES.filter((source) => source.type === tab.value)
                    .length,
          }))}
        />
        <button
          type="button"
          onClick={() => setSort(NEXT_SORT[sort])}
          className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-[10px] px-3 py-2 text-sm font-medium transition-colors hover:bg-surface-chip"
        >
          <ArrowUpDown className="h-4 w-4" />
          {SORT_LABELS[sort]}
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {sources.map((source) => {
          const meta = TYPE_META[source.type]
          return (
            <div
              key={source.name}
              className="flex min-w-0 cursor-pointer flex-col gap-2.5 rounded-2xl bg-white px-4 py-3.5 transition-shadow hover:shadow-[0_8px_24px_rgba(18,19,22,0.08)]"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="flex min-w-0 flex-col gap-px">
                  <span className="truncate text-[15px] font-semibold">
                    {source.name}
                  </span>
                  <span className="truncate text-[13px] text-ink-3">
                    {source.description}
                  </span>
                </span>
                <ArrowUpRight className="mt-0.5 h-4 w-4 shrink-0 text-ink-3" />
              </div>
              <div className="flex items-center justify-between gap-2">
                <span
                  className={cn(
                    'inline-flex whitespace-nowrap rounded-md px-[7px] py-[3px] text-xs font-semibold',
                    meta.className
                  )}
                >
                  {meta.label}
                </span>
                <span className="whitespace-nowrap text-xs text-ink-3">
                  {source.updated}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </>
  )
}

export default PulseSources
