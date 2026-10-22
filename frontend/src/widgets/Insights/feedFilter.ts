import type {
  IPulseInsight,
  PulseFactor,
  PulseHorizon,
  PulseKind,
  RelevanceLevel,
} from '@/store/models/IPulse'

export type FeedType = 'all' | PulseKind
export type FeedSort = 'relevance' | 'time'

export interface FeedFilters {
  type: FeedType
  factor: PulseFactor | null
  /** null — «Сейчас»: без ограничения по горизонту. */
  horizon: Exclude<PulseHorizon, 'now'> | null
  favoritesOnly: boolean
  sort: FeedSort
}

export interface FeedResult {
  items: IPulseInsight[]
  /** Счётчики вкладок: после фильтров фактора и горизонта, до типа. */
  counts: Record<FeedType, number>
}

const LEVEL_SCORE: Record<RelevanceLevel, number> = {
  high: 90,
  medium: 60,
  low: 30,
}

/** Релевантность числом: % из макета или уровень словами из API. */
const relevanceScore = (insight: IPulseInsight) =>
  insight.relevance ??
  (insight.relevanceLevel ? LEVEL_SCORE[insight.relevanceLevel] : 0)

const byRelevance = (a: IPulseInsight, b: IPulseInsight) =>
  // Новые — первыми, дальше по релевантности, при равенстве — свежие.
  Number(Boolean(b.isNew)) - Number(Boolean(a.isNew)) ||
  relevanceScore(b) - relevanceScore(a) ||
  a.ageHours - b.ageHours

const byTime = (a: IPulseInsight, b: IPulseInsight) => a.ageHours - b.ageHours

/** Отбор и сортировка ленты по фильтрам экрана. */
export const filterFeed = (
  insights: IPulseInsight[],
  filters: FeedFilters,
  favorites: string[]
): FeedResult => {
  const base = insights.filter(
    (insight) =>
      (!filters.factor || insight.factor === filters.factor) &&
      (!filters.horizon || insight.horizon === filters.horizon)
  )

  const counts: Record<FeedType, number> = {
    all: base.length,
    risk: 0,
    opp: 0,
    hyp: 0,
    mixed: 0,
    info: 0,
  }
  base.forEach((insight) => {
    counts[insight.kind] += 1
  })

  const items = base
    .filter(
      (insight) =>
        (filters.type === 'all' || insight.kind === filters.type) &&
        (!filters.favoritesOnly || favorites.includes(insight.id))
    )
    .sort(filters.sort === 'time' ? byTime : byRelevance)

  return { items, counts }
}

const FEED_TYPES: FeedType[] = ['all', 'risk', 'opp', 'hyp', 'mixed', 'info']
const FACTORS: PulseFactor[] = ['rate', 'fuel', 'cp', 'dem', 'reg', 'fx']

/** Фильтры из адреса: незнакомые значения игнорируются. */
export const filtersFromParams = (params: URLSearchParams): FeedFilters => {
  const type = params.get('type') as FeedType
  const factor = params.get('factor') as PulseFactor
  const horizon = params.get('h')
  return {
    type: FEED_TYPES.includes(type) ? type : 'all',
    factor: FACTORS.includes(factor) ? factor : null,
    horizon: horizon === 'm3' || horizon === 'm12' ? horizon : null,
    favoritesOnly: params.get('fav') === '1',
    sort: params.get('sort') === 'time' ? 'time' : 'relevance',
  }
}
