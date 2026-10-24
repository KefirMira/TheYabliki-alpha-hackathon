import { configureStore } from '@reduxjs/toolkit'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchInsightsFeed } from '@/shared/api/insights.api'
import type { IInsightFeedItem } from '@/store/models/IInsight'
import { setCurrentCompany } from '@/store/reducers/CompanySlice'
import { reducer } from '@/store/rootReducer'

import { getInsightsFeed } from './getInsightsFeed'
import { refreshInsightsFeed } from './refreshInsightsFeed'

vi.mock('@/shared/api/insights.api', () => ({
  fetchInsightsFeed: vi.fn(),
}))

const item = (id: number) =>
  ({ insight_id: id, company_id: 'DEMO-001' }) as IInsightFeedItem

const page = (ids: number[], next_cursor: string | null) => ({
  items: ids.map(item),
  next_cursor,
})

/** Стор с загруженной лентой из этих инсайтов. */
const storeWith = async (ids: number[]) => {
  const store = configureStore({ reducer })
  store.dispatch(setCurrentCompany('DEMO-001'))
  vi.mocked(fetchInsightsFeed).mockResolvedValueOnce(page(ids, null))
  await store.dispatch(getInsightsFeed({ companyId: 'DEMO-001' }))
  return store
}

describe('refreshInsightsFeed', () => {
  beforeEach(() => {
    vi.mocked(fetchInsightsFeed).mockReset()
  })

  it('идёт по страницам, пока не встретит загруженный инсайт', async () => {
    const store = await storeWith([2, 1])
    vi.mocked(fetchInsightsFeed)
      .mockResolvedValueOnce(page([5, 4], 'c1'))
      .mockResolvedValueOnce(page([3, 2], 'c2'))

    const result = await store.dispatch(
      refreshInsightsFeed({ companyId: 'DEMO-001' })
    )

    expect(fetchInsightsFeed).toHaveBeenLastCalledWith(
      expect.objectContaining({ cursor: 'c1' })
    )
    expect(result.payload).toMatchObject({ reachedKnown: true })
    expect(store.getState().insights.items.map((i) => i.insight_id)).toEqual([
      5, 4, 3, 2, 1,
    ])
  })

  it('пустая лента — одна страница и её курсор', async () => {
    const store = await storeWith([])
    vi.mocked(fetchInsightsFeed).mockResolvedValueOnce(page([3, 2], 'c1'))

    await store.dispatch(refreshInsightsFeed({ companyId: 'DEMO-001' }))

    expect(fetchInsightsFeed).toHaveBeenCalledTimes(2)
    expect(store.getState().insights.nextCursor).toBe('c1')
  })
})
