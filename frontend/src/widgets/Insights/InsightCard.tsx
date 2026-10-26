import type { MouseEvent } from 'react'
import { Bookmark } from 'lucide-react'
import { Link } from 'react-router-dom'

import { cn } from '@/lib/utils'
import type { IPulseInsight } from '@/store/models/IPulse'

import InsightKindTag from './InsightKindTag'
import { relevanceText } from './insightView'

interface InsightCardProps {
  insight: IPulseInsight
  /** Кнопка избранного в шапке — только в ленте. */
  favorite?: boolean
  onToggleFavorite?: (id: string) => void
}

/**
 * Карточка инсайта для сводки и ленты: тег типа и релевантность, заголовок,
 * смысл для компании, внизу — когда сделан анализ.
 */
const InsightCard = ({
  insight,
  favorite,
  onToggleFavorite,
}: InsightCardProps) => {
  const relevance = relevanceText(insight)

  const handleFavorite = (event: MouseEvent) => {
    // Кнопка внутри ссылки-карточки: переход по клику на неё не нужен.
    event.preventDefault()
    event.stopPropagation()
    onToggleFavorite?.(insight.id)
  }

  return (
    <Link
      to={`/pulse/insights/${insight.parentInsightId ?? insight.id}`}
      className="flex h-full min-w-0 flex-col gap-4 rounded-3xl bg-white p-5 transition-shadow hover:shadow-[0_8px_24px_rgba(18,19,22,0.08)]"
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
        {insight.meaning && (
          <p className={cn('text-sm leading-5 text-ink-2', insight.parentInsightId ? 'line-clamp-4' : 'truncate')}>
            {insight.meaning}
          </p>
        )}
      </div>

      {insight.parentInsightId && <div className="text-xs leading-5 text-ink-2">
        <p>Компания: {insight.companyName}</p>
        <p>Фрагмент сохранённого ответа LLM, не новый инсайт. Финансовая достоверность не подтверждена.</p>
        <p>Исходный инсайт #{insight.parentInsightId} · источники и журнал: evidence {insight.evidenceCount}, шагов {insight.traceSteps}.</p>
        <p>Источники относятся ко всему анализу и не доказывают автоматически этот пункт.</p>
      </div>}
      <div className="mt-auto flex min-w-0 items-center gap-1.5">
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
