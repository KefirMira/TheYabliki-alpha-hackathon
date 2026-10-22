import { cn } from '@/lib/utils'
import type { InsightType } from '@/store/models/IInsight'

import { insightTypeMeta } from './insightPresentation'

/** Тег типа инсайта: иконка + подпись мелким капсом на тонированной подложке. */
const InsightTypeTag = ({ type }: { type: InsightType | null }) => {
  const { label, icon: Icon, toneClass } = insightTypeMeta(type)

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-bold uppercase tracking-wide',
        toneClass
      )}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {label}
    </span>
  )
}

export default InsightTypeTag
