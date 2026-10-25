import { SAVED_PILOT_COMPANY } from '@/shared/constants/savedPilot'
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
  updated:
    (item.company_id === SAVED_PILOT_COMPANY
      ? 'Импорт сохранённого результата'
      : 'Анализ') +
    ' от ' +
    formatDay(item.created_at),
  ageHours: Math.max(0, (now - Date.parse(item.created_at)) / HOUR_MS),
})

const isSynthetic = (source: IApiSource) => source.synthetic === true

/**
 * Позиция Альфа-Банка — точный фрагмент из PDF базы знаний: корпус RAG
 * состоит из аналитики Альфа-Банка. Синтетические фикстуры позицией банка
 * не считаются — тогда страница явно пишет, что позиции нет.
 */
export const bankPositionFrom = (card: IInsightCard): IBankPosition | null => {
  const fragment = card.evidence.find((evidence: IApiEvidence) =>
    card.sources.some((source) => {
      const provenance = source.provenance as
        { publisher?: string; attribution_status?: string } | undefined
      return (
        !isSynthetic(source) &&
        source.document === evidence.document &&
        source.page === evidence.page &&
        source.chunk_id === evidence.chunk_id &&
        provenance?.attribution_status === 'VERIFIED' &&
        provenance.publisher === 'Альфа-Банк'
      )
    })
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
    passed === true
      ? 'техническая проверка пройдена; финансовая достоверность не установлена'
      : passed === false
        ? 'есть замечания; финансовая достоверность не установлена'
        : ''
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
        ? 'Техническая проверка пройдена; финансовая достоверность не установлена'
        : 'Техническая проверка: есть замечания; финансовая достоверность не установлена',
      description: warnings.join('; ') || 'Замечаний нет',
      warning: !passed,
    })
  }
  return steps
}

const financialReviewOf = (
  card: IInsightCard
): IInsightDetail['financialReview'] => {
  const value = card.validation.financial_review as
    { status?: unknown; findings?: unknown } | undefined
  if (
    !value ||
    typeof value.status !== 'string' ||
    !Array.isArray(value.findings)
  )
    return undefined
  return {
    status: value.status,
    findings: value.findings.filter(
      (
        v
      ): v is {
        code: string
        disposition: string
        claim: string
        explanation: string
      } =>
        v &&
        ['code', 'disposition', 'claim', 'explanation'].every(
          (k) => typeof v[k] === 'string'
        )
    ),
  }
}

const savedPilotOf = (card: IInsightCard): IInsightDetail['savedPilot'] => {
  const value = card.validation.saved_pilot_import as
    Record<string, unknown> | undefined
  if (
    !value ||
    value.version !== 'saved-llm-pilot-v1' ||
    value.synthetic !== true
  )
    return undefined
  const usage = value.usage as Record<string, unknown> | undefined
  if (
    !usage ||
    ![
      'prompt_tokens',
      'completion_tokens',
      'reasoning_tokens',
      'total_tokens',
    ].every((k) => Number.isInteger(usage[k]) && Number(usage[k]) >= 0)
  )
    return undefined
  if (
    !['model', 'pilot_date', 'imported_at', 'artifact_sha256'].every(
      (k) => typeof value[k] === 'string'
    ) ||
    typeof value.service_seconds !== 'number'
  )
    return undefined
  const trace = card.validation.orchestration as
    { events?: unknown } | undefined
  const events = Array.isArray(trace?.events)
    ? trace.events
        .filter(
          (e): e is { tool: string; reason: string } =>
            e && typeof e.tool === 'string' && typeof e.reason === 'string'
        )
        .map((e) => ({ tool: e.tool, reason: e.reason }))
    : []
  return {
    model: value.model as string,
    pilotDate: value.pilot_date as string,
    importedAt: value.imported_at as string,
    artifactSha256: value.artifact_sha256 as string,
    duration: value.service_seconds,
    usage: usage as NonNullable<IInsightDetail['savedPilot']>['usage'],
    events,
  }
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
      fact:
        card.news.text?.trim() ||
        'Текст новости отсутствует; доступен только заголовок.',
      synthetic:
        card.sources.some(isSynthetic) ||
        warnings.some((w) => w.startsWith('SYNTHETIC_')),
      impact: card.summary?.trim() ?? '',
      bank: bankPositionFrom(card),
      risks: card.risks,
      opportunities: card.opportunities,
      actions: card.recommendations,
      sources: card.sources.map((source) => ({
        name: source.document ?? 'Источник',
        description: [
          'Источник ' + String(source.id),
          source.page && `стр. ${source.page}`,
          source.date,
        ]
          .filter(Boolean)
          .join(' · '),
      })),
      evidence: card.evidence.map((evidence) => ({
        text: evidence.text,
        document: evidence.document,
        page: evidence.page,
      })),
      confidence,
      financialReview: financialReviewOf(card),
      savedPilot: savedPilotOf(card),
      warnings,
      logTime: formatDayTime(card.created_at),
      log: analysisLog(card),
    },
  }
}
