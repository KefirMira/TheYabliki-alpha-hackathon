import type {
  IPulseInsight,
  PulseKind,
  RelevanceLevel,
} from '@/store/models/IPulse'

export type FeedType = 'all' | PulseKind
export type FeedSort = 'relevance' | 'time'

export interface FeedFilters {
  type: FeedType
  favoritesOnly: boolean
  sort: FeedSort
}

export interface FeedResult {
  items: IPulseInsight[]
  /** Счётчики вкладок по типам — без учёта выбранного типа. */
  counts: Record<FeedType, number>
}

const LEVEL_SCORE: Record<RelevanceLevel, number> = {
  high: 3,
  medium: 2,
  low: 1,
}

const relevanceScore = (insight: IPulseInsight) =>
  insight.relevanceLevel ? LEVEL_SCORE[insight.relevanceLevel] : 0

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
  const counts: Record<FeedType, number> = {
    all: insights.length,
    risk: 0,
    opp: 0,
    mixed: 0,
    info: 0,
  }
  insights.forEach((insight) => {
    counts[insight.kind] += 1
  })

  const items = insights
    .filter(
      (insight) =>
        (filters.type === 'all' || insight.kind === filters.type) &&
        (!filters.favoritesOnly || favorites.includes(insight.id))
    )
    .sort(filters.sort === 'time' ? byTime : byRelevance)

  return { items, counts }
}

const FEED_TYPES: FeedType[] = ['all', 'risk', 'opp', 'mixed', 'info']

/** Фильтры из адреса: незнакомые значения игнорируются. */
export const filtersFromParams = (params: URLSearchParams): FeedFilters => {
  const type = params.get('type') as FeedType
  return {
    type: FEED_TYPES.includes(type) ? type : 'all',
    favoritesOnly: params.get('fav') === '1',
    sort: params.get('sort') === 'time' ? 'time' : 'relevance',
  }
}
