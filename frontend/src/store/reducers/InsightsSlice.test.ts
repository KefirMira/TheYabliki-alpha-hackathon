import { describe, expect, it } from 'vitest'

import type { IInsightFeedItem } from '../models/IInsight'
import { getInsightsFeed } from '../service/Insights/getInsightsFeed'
import { refreshInsightsFeed } from '../service/Insights/refreshInsightsFeed'
import { setCurrentCompany } from './CompanySlice'
import reducer, { type InsightsState, markInsightSeen } from './InsightsSlice'

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

const refreshStart = (requestId: string, companyId = 'DEMO-001') =>
  refreshInsightsFeed.pending(requestId, { companyId })

interface RefreshOptions {
  reachedKnown?: boolean
  nextCursor?: string | null
}

/** Ответ обновления: по умолчанию дошёл до уже загруженного инсайта. */
const refreshDone = (
  requestId: string,
  items: IInsightFeedItem[],
  companyId = 'DEMO-001',
  { reachedKnown = true, nextCursor = null }: RefreshOptions = {}
) =>
  refreshInsightsFeed.fulfilled(
    { items, reachedKnown, nextCursor },
    requestId,
    { companyId }
  )

/** Обновление целиком: запуск и ответ. */
const refreshed = (
  items: IInsightFeedItem[],
  companyId = 'DEMO-001',
  options: RefreshOptions = {}
) => [
  refreshStart('bg', companyId),
  refreshDone('bg', items, companyId, options),
]

describe('InsightsSlice: фоновое обновление', () => {
  const loaded = () => [start('r1'), done('r1', [item(2), item(1)], 'c1')]

  it('дописывает только новые инсайты сверху и помечает их новыми', () => {
    const state = run(...loaded(), ...refreshed([item(4), item(3)]))

    expect(state.items.map((i) => i.insight_id)).toEqual([4, 3, 2, 1])
    expect(state.newIds).toEqual([4, 3])
    // Курсор догрузки не сбрасывается.
    expect(state.nextCursor).toBe('c1')
  })

  it('открытый инсайт перестаёт быть новым', () => {
    const state = run(...loaded(), ...refreshed([item(3)]), markInsightSeen(3))

    expect(state.newIds).toEqual([])
  })

  it('ответ по другой компании и во время загрузки отбрасывается', () => {
    const otherCompany = run(...loaded(), ...refreshed([item(9)], 'DEMO-002'))
    const whileLoading = run(start('r1'), ...refreshed([item(9)]))

    expect(otherCompany.items.map((i) => i.insight_id)).toEqual([2, 1])
    expect(whileLoading.items).toEqual([])
  })

  it('новая загрузка первой страницы снимает пометки', () => {
    const state = run(
      ...loaded(),
      ...refreshed([item(3)]),
      start('r2'),
      done('r2', [item(3), item(2), item(1)], null)
    )

    expect(state.newIds).toEqual([])
  })

  it('пустая лента: новые страницы и курсор — «Показать ещё» на месте', () => {
    // 51 новый инсайт: обновление принесло первую страницу и курсор.
    const fresh = Array.from({ length: 50 }, (_, index) => item(51 - index))
    const state = run(
      start('r1'),
      done('r1', [], null),
      ...refreshed(fresh, 'DEMO-001', { reachedKnown: false, nextCursor: 'c2' })
    )

    expect(state.items).toHaveLength(50)
    expect(state.nextCursor).toBe('c2')
    expect(state.newIds).toHaveLength(50)
  })

  it('не дошли до загруженного — лента заменяется, курсор продолжает её', () => {
    const state = run(
      ...loaded(),
      ...refreshed([item(9), item(8)], 'DEMO-001', {
        reachedKnown: false,
        nextCursor: 'c9',
      })
    )

    expect(state.items.map((i) => i.insight_id)).toEqual([9, 8])
    expect(state.nextCursor).toBe('c9')
  })

  it('поздний ответ раннего обновления не затирает свежую ленту', () => {
    const replace = { reachedKnown: false, nextCursor: null }
    const state = run(
      ...loaded(),
      // Фоновое обновление и «Обновить» запущены одно за другим.
      refreshStart('old'),
      refreshStart('new'),
      refreshDone('new', [item(2), item(1)], 'DEMO-001', replace),
      refreshDone('old', [item(1)], 'DEMO-001', replace)
    )

    expect(state.items.map((i) => i.insight_id)).toEqual([2, 1])
  })

  it('загрузка первой страницы отменяет идущее обновление', () => {
    const state = run(
      ...loaded(),
      refreshStart('bg'),
      start('r2'),
      done('r2', [item(3), item(2), item(1)], null),
      refreshDone('bg', [item(1)], 'DEMO-001', { reachedKnown: false })
    )

    expect(state.items.map((i) => i.insight_id)).toEqual([3, 2, 1])
  })

  it('неудачное обновление отмечается — для проверки готовности сервиса', () => {
    const state = run(
      ...loaded(),
      refreshStart('bg'),
      refreshInsightsFeed.rejected(null, 'bg', { companyId: 'DEMO-001' })
    )

    expect(state.refreshFailedAt).not.toBeNull()
    expect(state.items).toHaveLength(2)
  })
})
