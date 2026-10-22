import type { MouseEvent } from 'react'
import { Bookmark, Check, X } from 'lucide-react'
import { Link } from 'react-router-dom'

import { cn } from '@/lib/utils'
import Chip from '@/shared/ui/Chip'
import type { IPulseInsight } from '@/store/models/IPulse'

import InsightKindTag from './InsightKindTag'
import { fitChips, relevanceText } from './insightView'

interface InsightCardProps {
  insight: IPulseInsight
  /** Кнопка избранного в шапке — только в ленте. */
  favorite?: boolean
  onToggleFavorite?: (id: string) => void
}

/**
 * Карточка инсайта для сводки и ленты. Одна анатомия: тег и релевантность,
 * заголовок, смысл для компании (у гипотезы — что подтверждает и что нет),
 * внизу чипы «почему вам» и свежесть.
 */
const InsightCard = ({
  insight,
  favorite,
  onToggleFavorite,
}: InsightCardProps) => {
  const { visible, more } = fitChips(insight.chips)
  const isHyp = insight.kind === 'hyp' && Boolean(insight.pro || insight.con)
  const relevance = relevanceText(insight)

  const handleFavorite = (event: MouseEvent) => {
    // Кнопка внутри ссылки-карточки: переход по клику на неё не нужен.
    event.preventDefault()
    event.stopPropagation()
    onToggleFavorite?.(insight.id)
  }

  return (
    <Link
      to={`/pulse/insights/${insight.id}`}
      className="flex h-full min-w-0 flex-col gap-4 rounded-[20px] bg-white p-5 transition-shadow hover:shadow-[0_8px_24px_rgba(18,19,22,0.08)]"
    >
      <div className="flex min-w-0 items-center justify-between gap-2">
        <span className="shrink-0">
          <InsightKindTag insight={insight} />
        </span>
        <span className="flex min-w-0 items-center gap-1.5">
          {relevance && (
            <span className="truncate text-[13px] font-semibold text-ink-2">
              {relevance}
            </span>
          )}
          {onToggleFavorite && (
            <button
              type="button"
              onClick={handleFavorite}
              aria-pressed={favorite}
              aria-label={favorite ? 'Убрать из избранного' : 'В избранное'}
              className={cn(
                '-my-1 -mr-1.5 flex h-7 w-7 items-center justify-center rounded-lg transition-colors hover:bg-surface-page',
                favorite ? 'text-brand' : 'text-ink-4'
              )}
            >
              <Bookmark
                className="h-4 w-4"
                fill={favorite ? 'currentColor' : 'none'}
              />
            </button>
          )}
        </span>
      </div>

      <div className="flex min-w-0 flex-col gap-1.5">
        <h3 className="line-clamp-2 min-h-6 text-[17px] font-semibold leading-6 text-pretty">
          {insight.title}
        </h3>
        {isHyp ? (
          <div className="flex flex-col gap-1 text-sm leading-5 text-ink-2">
            <span className="flex min-w-0 items-center gap-1.5">
              <Check className="h-3.5 w-3.5 shrink-0 text-tone-opp-fg" />
              <span className="truncate">{insight.pro}</span>
            </span>
            <span className="flex min-w-0 items-center gap-1.5">
              <X className="h-3.5 w-3.5 shrink-0 text-tone-risk-fg" />
              <span className="truncate">{insight.con}</span>
            </span>
          </div>
        ) : (
          insight.meaning && (
            <p className="truncate text-sm leading-5 text-ink-2">
              {insight.meaning}
            </p>
          )
        )}
      </div>

      <div className="mt-auto flex min-w-0 items-center gap-1.5">
        <div className="flex h-6 min-w-0 flex-wrap gap-1.5 overflow-hidden">
          {visible.map((chip) => (
            <Chip key={chip}>{chip}</Chip>
          ))}
        </div>
        {more > 0 && (
          <span className="whitespace-nowrap text-xs text-ink-3">+{more}</span>
        )}
        <span className="flex-1" />
        {insight.isNew && (
          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-tone-info-fg" />
        )}
        <span
          className={cn(
            'whitespace-nowrap text-xs',
            insight.isNew ? 'font-semibold text-tone-info-fg' : 'text-ink-3'
          )}
        >
          {insight.updated}
        </span>
      </div>
    </Link>
  )
}

export default InsightCard
