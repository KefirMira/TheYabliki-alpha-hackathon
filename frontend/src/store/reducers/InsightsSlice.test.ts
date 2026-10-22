import { describe, expect, it } from 'vitest'

import type { IInsightFeedItem } from '../models/IInsight'
import { getInsightsFeed } from '../service/Insights/getInsightsFeed'
import { setCurrentCompany } from './CompanySlice'
import reducer, { type InsightsState } from './InsightsSlice'

const item = (id: number): IInsightFeedItem => ({
  insight_id: id,
  run_id: id,
  company_id: 'DEMO-001',
  type: 'risk',
  relevance: 'unknown',
  summary: `Инсайт ${id}`,
  created_at: '2026-01-03T12:00:00Z',
  status: 'COMPLETED',
})

const start = (requestId: string, cursor?: string, companyId = 'DEMO-001') =>
  getInsightsFeed.pending(requestId, { companyId, cursor })

const done = (
  requestId: string,
  items: IInsightFeedItem[],
  next_cursor: string | null,
  cursor?: string
) =>
  getInsightsFeed.fulfilled({ items, next_cursor }, requestId, {
    companyId: 'DEMO-001',
    cursor,
  })

const run = (...actions: Parameters<typeof reducer>[1][]): InsightsState =>
  actions.reduce(reducer, reducer(undefined, { type: '@@init' }))

describe('InsightsSlice', () => {
  it('первая страница заменяет ленту и запоминает курсор', () => {
    const state = run(start('r1'), done('r1', [item(2), item(1)], 'c1'))

    expect(state.items.map((i) => i.insight_id)).toEqual([2, 1])
    expect(state.nextCursor).toBe('c1')
    expect(state.isInitialized).toBe(true)
    expect(state.loadingList).toBe(false)
  })

  it('страница по курсору дописывается без дублей', () => {
    const state = run(
      start('r1'),
      done('r1', [item(3), item(2)], 'c1'),
      start('r2', 'c1'),
      done('r2', [item(2), item(1)], null, 'c1')
    )

    expect(state.items.map((i) => i.insight_id)).toEqual([3, 2, 1])
    expect(state.nextCursor).toBeNull()
    expect(state.loadingMore).toBe(false)
  })

  it('ответ устаревшего запроса не попадает в ленту', () => {
    // Пользователь сменил компанию, пока грузилась лента прежней.
    const state = run(
      start('old'),
      start('new', undefined, 'DEMO-002'),
      done('old', [item(9)], null)
    )

    expect(state.companyId).toBe('DEMO-002')
    expect(state.items).toEqual([])
    expect(state.loadingList).toBe(true)
  })

  it('ответ прежней компании до запроса новой не попадает в ленту', () => {
    // Смена компании уже в сторе, а лента новой ещё не начала грузиться.
    const state = run(
      start('r1'),
      setCurrentCompany('DEMO-002'),
      done('r1', [item(9)], 'c1')
    )

    expect(state.items).toEqual([])
    expect(state.nextCursor).toBeNull()
    expect(state.isInitialized).toBe(false)
  })

  it('ошибка догрузки не стирает уже показанную ленту', () => {
    const state = run(
      start('r1'),
      done('r1', [item(2)], 'c1'),
      start('r2', 'c1'),
      getInsightsFeed.rejected(
        null,
        'r2',
        {
          companyId: 'DEMO-001',
          cursor: 'c1',
        },
        'Сеть недоступна'
      )
    )

    expect(state.items).toHaveLength(1)
    expect(state.errorMore).toBe('Сеть недоступна')
    expect(state.error).toBeUndefined()
  })
})
