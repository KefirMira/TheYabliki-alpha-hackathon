import { format, parseISO } from 'date-fns'
import { ru } from 'date-fns/locale'

import type {
  IInsightCard,
  IInsightEvidence as IApiEvidence,
  IInsightFeedItem,
  IInsightSource as IApiSource,
  InsightType,
} from '@/store/models/IInsight'
import type {
  IAnalysisStep,
  IBankPosition,
  IInsightDetail,
  IPulseInsight,
  PulseKind,
} from '@/store/models/IPulse'

/**
 * Ответы API → модели экранов. Правило одно: ничего не выдумываем. Чего нет в
 * ответе, того нет и в модели — пустой список или пустая строка, и блок на
 * странице не показывается.
 */

const KIND_BY_TYPE: Record<InsightType, PulseKind> = {
  risk: 'risk',
  opportunity: 'opp',
  mixed: 'mixed',
  information: 'info',
}

const HOUR_MS = 3_600_000

export const formatDay = (iso: string) =>
  format(parseISO(iso), 'd MMMM yyyy', { locale: ru })

export const formatDayTime = (iso: string) =>
  format(parseISO(iso), 'd MMMM yyyy, HH:mm', { locale: ru })

/** Строка ленты → карточка инсайта. created_at — время анализа, не новости. */
export const mapFeedItem = (
  item: IInsightFeedItem,
  now = Date.now()
): IPulseInsight => ({
  id: String(item.insight_id),
  // Тип не определён — нейтральная «информация», а не догадка.
  kind: item.type ? KIND_BY_TYPE[item.type] : 'info',
  relevanceLevel:
    item.relevance && item.relevance !== 'unknown' ? item.relevance : undefined,
  title: item.summary?.trim() || 'Инсайт без описания',
  chips: [],
  updated: `Анализ от ${formatDay(item.created_at)}`,
  ageHours: Math.max(0, (now - Date.parse(item.created_at)) / HOUR_MS),
})

const isSynthetic = (source: IApiSource) => source.synthetic === true

/**
 * Позиция Альфа-Банка — точный фрагмент из PDF базы знаний: корпус RAG
 * состоит из аналитики Альфа-Банка. Синтетические фикстуры позицией банка
 * не считаются — тогда страница явно пишет, что позиции нет.
 */
export const bankPositionFrom = (card: IInsightCard): IBankPosition | null => {
  const synthetic = new Set(
    card.sources.filter(isSynthetic).map((source) => source.document)
  )
  const fragment = card.evidence.find(
    (evidence: IApiEvidence) =>
      evidence.evidence_type.toUpperCase() === 'PDF' &&
      !synthetic.has(evidence.document ?? undefined)
  )
  if (!fragment) return null

  const sourceDate = card.sources.find(
    (source) => source.document === fragment.document
  )?.date
  return {
    author: 'Аналитика Альфа-Банка',
    date: fragment.document_date
      ? formatDay(fragment.document_date)
      : (sourceDate ?? ''),
    quote: fragment.text,
    document: [fragment.document, fragment.page && `стр. ${fragment.page}`]
      .filter(Boolean)
      .join(' · '),
  }
}

const validationOf = (card: IInsightCard) => {
  const warnings = (card.validation.warnings ?? []).filter(Boolean)
  const passed = card.validation.passed
  // Пустой validation старой записи — проверки не было, не «пройдена».
  const confidence =
    passed === true ? 'пройдена' : passed === false ? 'есть замечания' : ''
  return { warnings, passed, confidence }
}

/** Ход анализа — только из того, что есть в ответе API. */
const analysisLog = (card: IInsightCard): IAnalysisStep[] => {
  const documents = [
    ...new Set(card.sources.map((source) => source.document).filter(Boolean)),
  ]
  const { warnings, passed } = validationOf(card)
  const steps: IAnalysisStep[] = [
    { title: 'Получена новость', description: card.news.title },
    {
      title: `Найдено источников: ${card.sources.length}`,
      description: documents.join(', ') || 'Источники не найдены',
    },
    {
      title: `Сохранено фрагментов-доказательств: ${card.evidence.length}`,
      description: 'Точные цитаты из материалов, без пересказа',
    },
  ]
  if (passed !== undefined) {
    steps.push({
      title: passed
        ? 'Проверка достоверности пройдена'
        : 'Проверка достоверности: есть замечания',
      description: warnings.join('; ') || 'Замечаний нет',
      warning: !passed,
    })
  }
  return steps
}

/** Карточка API → шапка инсайта и содержимое страницы. */
export const mapInsightCard = (
  card: IInsightCard,
  now = Date.now()
): { insight: IPulseInsight; detail: IInsightDetail } => {
  const { warnings, confidence } = validationOf(card)
  const insight: IPulseInsight = {
    ...mapFeedItem(card, now),
    title: card.news.title,
    meaning: card.summary?.trim() || undefined,
  }

  return {
    insight,
    detail: {
      fact: card.news.text?.trim() || card.news.title,
      impact: card.summary?.trim() ?? '',
      figures: [],
      bank: bankPositionFrom(card),
      affected: [],
      risks: card.risks,
      opportunities: card.opportunities,
      actions: card.recommendations.map((text) => ({
        title: text,
        description: '',
      })),
      scenarios: [],
      sources: card.sources.map((source) => ({
        name: source.document ?? 'Источник',
        description: [source.page && `стр. ${source.page}`, source.date]
          .filter(Boolean)
          .join(' · '),
      })),
      evidence: card.evidence.map((evidence) => ({
        text: evidence.text,
        document: evidence.document,
        page: evidence.page,
      })),
      confidence,
      warnings,
      logTime: formatDayTime(card.created_at),
      log: analysisLog(card),
      questions: [],
    },
  }
}
