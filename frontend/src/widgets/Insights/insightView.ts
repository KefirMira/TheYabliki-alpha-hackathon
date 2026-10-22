import {
  ArrowDownRight,
  ArrowLeftRight,
  ArrowUpRight,
  CircleHelp,
  Info,
  type LucideIcon,
} from 'lucide-react'

import type { TagTone } from '@/shared/ui/tagTones'
import type {
  ImpactLevel,
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
  hyp: { label: 'Гипотеза', icon: CircleHelp, tone: 'hyp' },
  mixed: { label: 'Риск и возможность', icon: ArrowLeftRight, tone: 'info' },
  info: { label: 'Информация', icon: Info, tone: 'muted' },
}

export const LEVEL_TAG: Record<ImpactLevel, string> = {
  1: 'Низкое',
  2: 'Среднее',
  3: 'Высокое',
}

export const LEVEL_LABEL: Record<ImpactLevel, string> = {
  1: 'Низкая',
  2: 'Средняя',
  3: 'Высокая',
}

const RELEVANCE_LABEL: Record<RelevanceLevel, string> = {
  high: 'Высокая релевантность',
  medium: 'Средняя релевантность',
  low: 'Низкая релевантность',
}

/** «РИСК · ВЫСОКОЕ»; без уровня влияния (API) — только тип. */
export const kindTagText = (insight: IPulseInsight) => {
  const label = KIND_META[insight.kind].label
  return insight.level ? `${label} · ${LEVEL_TAG[insight.level]}` : label
}

/**
 * Справа в шапке карточки: сила данных у гипотезы, релевантность в % или
 * словами (как отдаёт API). Нет данных — пустая строка, ничего не рисуем.
 */
export const relevanceText = (insight: IPulseInsight, long = false) => {
  if (insight.kind === 'hyp' && insight.strength) {
    return `Сила данных: ${insight.strength}`
  }
  if (insight.relevance !== undefined) {
    return long
      ? `Релевантность для вас: ${insight.relevance}%`
      : `${insight.relevance}%`
  }
  return insight.relevanceLevel ? RELEVANCE_LABEL[insight.relevanceLevel] : ''
}

/**
 * Чипы «почему вам», которые помещаются в одну строку карточки: не больше
 * двух и в пределах бюджета символов. Остальные — счётчиком «+N».
 */
export const fitChips = (chips: string[], budget = 18) => {
  let used = 0
  let shown = 0
  for (const chip of chips) {
    if (shown >= 2 || (shown > 0 && used + chip.length > budget)) break
    used += chip.length
    shown += 1
  }
  return { visible: chips.slice(0, shown), more: chips.length - shown }
}
