import { describe, expect, it } from 'vitest'

import type { IPulseInsight } from '@/store/models/IPulse'

import { type FeedFilters, filterFeed, filtersFromParams } from './feedFilter'

const insight = (
  id: string,
  patch: Partial<IPulseInsight> = {}
): IPulseInsight => ({
  id,
  kind: 'risk',
  title: `Инсайт ${id}`,
  updated: 'Анализ от 2 января 2026',
  ageHours: Number(id),
  ...patch,
})

// Возраст в часах = id: «1» — самый свежий.
const feed = [
  insight('1', { kind: 'info' }),
  insight('2', { kind: 'opp', relevanceLevel: 'high' }),
  insight('3', { relevanceLevel: 'medium' }),
  insight('4', { kind: 'mixed', isNew: true }),
  insight('5', { relevanceLevel: 'high' }),
]

const filters = (overrides: Partial<FeedFilters> = {}): FeedFilters => ({
  type: 'all',
  favoritesOnly: false,
  sort: 'relevance',
  ...overrides,
})

describe('filterFeed', () => {
  it('счётчики вкладок по типам из API', () => {
    expect(filterFeed(feed, filters(), []).counts).toEqual({
      all: 5,
      risk: 2,
      opp: 1,
      mixed: 1,
      info: 1,
    })
  })

  it('по важности: новое первым, дальше релевантность, при равенстве — свежие', () => {
    const { items } = filterFeed(feed, filters(), [])
    expect(items.map((i) => i.id)).toEqual(['4', '2', '5', '3', '1'])
  })

  it('фильтр типа не меняет счётчики вкладок', () => {
    const { items, counts } = filterFeed(feed, filters({ type: 'risk' }), [])
    expect(items.map((i) => i.id)).toEqual(['5', '3'])
    expect(counts.all).toBe(5)
  })

  it('только избранное', () => {
    const { items } = filterFeed(feed, filters({ favoritesOnly: true }), [
      '3',
      '1',
    ])
    expect(items.map((i) => i.id)).toEqual(['3', '1'])
  })

  it('по времени: свежие первыми', () => {
    const { items } = filterFeed(feed, filters({ sort: 'time' }), [])
    expect(items.map((i) => i.id)).toEqual(['1', '2', '3', '4', '5'])
  })
})

describe('filtersFromParams', () => {
  it('читает фильтры из адреса', () => {
    expect(
      filtersFromParams(new URLSearchParams('type=mixed&fav=1&sort=time'))
    ).toEqual({ type: 'mixed', favoritesOnly: true, sort: 'time' })
  })

  it('незнакомые значения — фильтры по умолчанию', () => {
    expect(filtersFromParams(new URLSearchParams('type=x&sort=z'))).toEqual(
      filters()
    )
  })
})
