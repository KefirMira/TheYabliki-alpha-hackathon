import Tag from '@/shared/ui/Tag'
import type { IPulseInsight } from '@/store/models/IPulse'

import { KIND_META } from './insightView'

/** Тег типа инсайта («РИСК») с иконкой. */
const InsightKindTag = ({
  insight,
  withIcon = true,
}: {
  insight: IPulseInsight
  withIcon?: boolean
}) => {
  const { icon: Icon, tone, label } = KIND_META[insight.kind]
  return (
    <Tag
      tone={tone}
      icon={withIcon ? <Icon className="h-3 w-3" strokeWidth={2.4} /> : null}
    >
      {label}
    </Tag>
  )
}

export default InsightKindTag
