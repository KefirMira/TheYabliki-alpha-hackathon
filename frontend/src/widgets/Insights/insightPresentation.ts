import { format, parseISO } from 'date-fns'
import { ru } from 'date-fns/locale'
import {
  ArrowDownRight,
  ArrowLeftRight,
  ArrowUpRight,
  Info,
  type LucideIcon,
} from 'lucide-react'

import type { InsightRelevance, InsightType } from '@/store/models/IInsight'

interface InsightTypeMeta {
  label: string
  icon: LucideIcon
  /** Подложка и текст тега — одного цветового семейства. */
  toneClass: string
}

const TYPE_META: Record<InsightType, InsightTypeMeta> = {
  risk: {
    label: 'Риск',
    icon: ArrowDownRight,
    toneClass: 'bg-tone-risk text-tone-risk-foreground',
  },
  opportunity: {
    label: 'Возможность',
    icon: ArrowUpRight,
    toneClass: 'bg-tone-opportunity text-tone-opportunity-foreground',
  },
  mixed: {
    label: 'Риск и возможность',
    icon: ArrowLeftRight,
    toneClass: 'bg-tone-mixed text-tone-mixed-foreground',
  },
  information: {
    label: 'Информация',
    icon: Info,
    toneClass: 'bg-tone-neutral text-tone-neutral-foreground',
  },
}

// Тип не определён бэкендом — показываем нейтральный тег, а не угадываем.
const UNKNOWN_TYPE_META: InsightTypeMeta = {
  label: 'Инсайт',
  icon: Info,
  toneClass: 'bg-tone-neutral text-tone-neutral-foreground',
}

export const insightTypeMeta = (type: InsightType | null): InsightTypeMeta =>
  (type && TYPE_META[type]) || UNKNOWN_TYPE_META

const RELEVANCE_LABELS: Record<Exclude<InsightRelevance, 'unknown'>, string> = {
  high: 'Высокая релевантность',
  medium: 'Средняя релевантность',
  low: 'Низкая релевантность',
}

/** Подпись релевантности; для `unknown` и null — ничего не показываем. */
export const relevanceLabel = (
  relevance: InsightRelevance | null
): string | null =>
  relevance && relevance !== 'unknown' ? RELEVANCE_LABELS[relevance] : null

/** «3 января 2026, 15:00» — в часовом поясе браузера. */
export const formatInsightDate = (iso: string): string =>
  format(parseISO(iso), 'd MMMM yyyy, HH:mm', { locale: ru })
