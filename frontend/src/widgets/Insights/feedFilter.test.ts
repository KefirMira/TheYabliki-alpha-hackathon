import { describe, expect, it } from 'vitest'

import { FEED_INSIGHT_IDS, PULSE_INSIGHTS } from '@/shared/mocks/pulse'

import { type FeedFilters, filterFeed, filtersFromParams } from './feedFilter'

const feed = FEED_INSIGHT_IDS.map((id) => PULSE_INSIGHTS[id])

const filters = (overrides: Partial<FeedFilters> = {}): FeedFilters => ({
  type: 'all',
  factor: null,
  horizon: null,
  favoritesOnly: false,
  sort: 'relevance',
  ...overrides,
})

describe('filterFeed', () => {
  it('счётчики вкладок совпадают с макетом: 10 · 4 · 2 · 4', () => {
    const { counts } = filterFeed(feed, filters(), [])
    expect(counts).toEqual({
      all: 10,
      risk: 4,
      opp: 2,
      hyp: 4,
      mixed: 0,
      info: 0,
    })
  })

  it('по важности: новое первым, дальше по релевантности', () => {
    const { items } = filterFeed(feed, filters(), [])
    expect(items.map((i) => i.id)).toEqual([
      'eu',
      'rate',
      'fuel',
      'supp',
      'ofz',
      'budget',
      'cp',
      'h1',
      'dem',
      'h2',
    ])
  })

  it('фильтр типа не меняет счётчики вкладок', () => {
    const { items, counts } = filterFeed(feed, filters({ type: 'hyp' }), [])
    expect(items.every((i) => i.kind === 'hyp')).toBe(true)
    expect(counts.all).toBe(10)
  })

  it('фактор и горизонт сужают и ленту, и счётчики', () => {
    const { items, counts } = filterFeed(
      feed,
      filters({ factor: 'fuel', horizon: 'm3' }),
      []
    )
    expect(items.map((i) => i.id).sort()).toEqual(['h1', 'supp'])
    expect(counts).toEqual({
      all: 2,
      risk: 1,
      opp: 0,
      hyp: 1,
      mixed: 0,
      info: 0,
    })
  })

  it('только избранное', () => {
    const { items } = filterFeed(feed, filters({ favoritesOnly: true }), [
      'rate',
      'h1',
    ])
    expect(items.map((i) => i.id)).toEqual(['rate', 'h1'])
  })

  it('по времени: свежие первыми', () => {
    const { items } = filterFeed(feed, filters({ sort: 'time' }), [])
    expect(items[0].id).toBe('eu')
    expect(items.at(-1)?.id).toBe('dem')
  })
})

describe('filtersFromParams', () => {
  it('читает фильтры из адреса', () => {
    expect(
      filtersFromParams(
        new URLSearchParams('type=risk&factor=rate&h=m12&fav=1&sort=time')
      )
    ).toEqual({
      type: 'risk',
      factor: 'rate',
      horizon: 'm12',
      favoritesOnly: true,
      sort: 'time',
    })
  })

  it('незнакомые значения — фильтры по умолчанию', () => {
    expect(
      filtersFromParams(new URLSearchParams('type=x&factor=y&h=now&sort=z'))
    ).toEqual(filters())
  })
})
