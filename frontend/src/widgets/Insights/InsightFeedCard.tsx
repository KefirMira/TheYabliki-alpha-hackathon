import type { IInsightFeedItem } from '@/store/models/IInsight'

import InsightTypeTag from './InsightTypeTag'
import { formatInsightDate, relevanceLabel } from './insightPresentation'

/**
 * Карточка ленты. Анатомия из макета: тег типа и релевантность сверху,
 * текст, внизу — дата. Лента отдаёт только summary, поэтому он и есть
 * основной текст карточки; заголовок и «почему вам» появятся вместе с
 * соответствующими полями API.
 */
const InsightFeedCard = ({ insight }: { insight: IInsightFeedItem }) => {
  const relevance = relevanceLabel(insight.relevance)

  return (
    <article className="flex h-full flex-col gap-3 rounded-lg bg-card p-5 transition-shadow hover:shadow-md">
      <div className="flex items-center justify-between gap-3">
        <InsightTypeTag type={insight.type} />
        {relevance && (
          <span className="text-xs text-muted-foreground">{relevance}</span>
        )}
      </div>

      <p className="line-clamp-3 text-[15px] font-semibold leading-snug">
        {insight.summary ?? 'Описание инсайта отсутствует'}
      </p>

      <p className="mt-auto text-xs text-muted-foreground">
        Анализ от {formatInsightDate(insight.created_at)}
      </p>
    </article>
  )
}

export default InsightFeedCard
