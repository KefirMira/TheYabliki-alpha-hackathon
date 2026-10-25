import {
  ArrowDownRight,
  ArrowLeftRight,
  ArrowUpRight,
  Info,
  type LucideIcon,
} from 'lucide-react'

import type { TagTone } from '@/shared/ui/tagTones'
import type {
  IPulseInsight,
  PulseKind,
  RelevanceLevel,
} from '@/store/models/IPulse'

interface KindMeta {
  label: string
  icon: LucideIcon
  tone: TagTone
}

export const KIND_META: Record<PulseKind, KindMeta> = {
  risk: { label: 'Риск', icon: ArrowDownRight, tone: 'risk' },
  opp: { label: 'Возможность', icon: ArrowUpRight, tone: 'opp' },
  mixed: { label: 'Риск и возможность', icon: ArrowLeftRight, tone: 'info' },
  info: { label: 'Информация', icon: Info, tone: 'muted' },
}

const RELEVANCE_LABEL: Record<RelevanceLevel, string> = {
  high: 'Высокая релевантность',
  medium: 'Средняя релевантность',
  low: 'Низкая релевантность',
}

/** Релевантность словами, как её отдаёт API. Нет — пустая строка. */
export const relevanceText = (insight: IPulseInsight) =>
  insight.relevanceLevel ? RELEVANCE_LABEL[insight.relevanceLevel] : ''
