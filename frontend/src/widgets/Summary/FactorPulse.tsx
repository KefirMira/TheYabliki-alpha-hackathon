import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import { cn } from '@/lib/utils'
import { FACTOR_TOPICS, PULSE_INSIGHTS } from '@/shared/mocks/pulse'
import Card from '@/shared/ui/Card'
import ImpactBars from '@/shared/ui/ImpactBars'
import Tag from '@/shared/ui/Tag'
import { plural } from '@/shared/utils/plural'
import type { ImpactLevel, PulseKind } from '@/store/models/IPulse'

import { FACTOR_ICONS } from './factorIcons'

const KIND_FORMS: Record<PulseKind, [string, string, string]> = {
  risk: ['риск', 'риска', 'рисков'],
  opp: ['возможность', 'возможности', 'возможностей'],
  hyp: ['гипотеза', 'гипотезы', 'гипотез'],
  mixed: ['риск и возможность', 'риска и возможности', 'рисков и возможностей'],
  info: ['событие', 'события', 'событий'],
}

const IMPACT_LABEL: Record<ImpactLevel, string> = {
  1: 'Низкое влияние',
  2: 'Среднее влияние',
  3: 'Высокое влияние',
}

/**
 * «Что сейчас влияет на компанию». Это не статичная карта: строки собраны
 * из текущих инсайтов, сгруппированных по факторам, новая тема появляется
 * сама. Клик открывает ленту с фильтром по фактору.
 */
const FactorPulse = () => (
  <Card className="gap-1 pb-2.5">
    <div className="flex items-center justify-between gap-4 pb-1.5">
      <span className="text-[17px] font-semibold leading-6">
        Что сейчас влияет на компанию
      </span>
      <span className="text-[13px] text-ink-3">
        Темы появляются автоматически из найденных событий
      </span>
    </div>

    {FACTOR_TOPICS.map((topic) => {
      const insights = topic.insightIds.map((id) => PULSE_INSIGHTS[id])
      const level = Math.max(...insights.map((i) => i.level)) as ImpactLevel
      const kinds = (['risk', 'opp', 'hyp'] as PulseKind[])
        .map(
          (kind) =>
            [kind, insights.filter((i) => i.kind === kind).length] as const
        )
        .filter(([, count]) => count > 0)
        .map(([kind, count]) => plural(count, KIND_FORMS[kind]))
        .join(', ')
      const Icon = FACTOR_ICONS[topic.factor]

      return (
        <Link
          key={topic.factor}
          to={`/pulse/insights?factor=${topic.factor}`}
          className="-mx-3 grid grid-cols-[minmax(0,1.1fr)_minmax(0,1.6fr)_180px_20px] items-center gap-4 rounded-xl border-t border-line-soft px-3 py-[9px] transition-colors hover:bg-surface-page"
        >
          <span className="flex min-w-0 items-center gap-3">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-surface-page text-ink-2">
              <Icon className="h-4 w-4" />
            </span>
            <span className="whitespace-nowrap text-[15px] font-semibold">
              {topic.title}
            </span>
            {topic.isNew && (
              <Tag tone="info" className="px-[7px] py-[3px]">
                Новая тема
              </Tag>
            )}
          </span>
          <span className="truncate text-sm text-ink-2">
            <b className="font-semibold text-ink">
              {plural(insights.length, ['инсайт', 'инсайта', 'инсайтов'])}
            </b>{' '}
            · {kinds}
          </span>
          <span className="flex items-center gap-2">
            <ImpactBars level={level} />
            <span
              className={cn(
                'text-[13px]',
                level === 3
                  ? 'font-semibold text-tone-risk-fg'
                  : 'font-medium text-ink-2'
              )}
            >
              {IMPACT_LABEL[level]}
            </span>
          </span>
          <ChevronRight className="h-4 w-4 text-ink-4" />
        </Link>
      )
    })}
  </Card>
)

export default FactorPulse
