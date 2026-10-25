import { createAsyncThunk } from '@reduxjs/toolkit'

import { fetchInsightsFeed } from '@/shared/api/insights.api'
import { INITIAL_FEED_LIMIT } from '@/shared/constants/insights'
import type { IInsightFeedItem } from '@/store/models/IInsight'

/** Сколько страниц догружать, пока не встретится уже загруженный инсайт. */
const MAX_REFRESH_PAGES = 5

export interface RefreshedFeed {
  /** Свежие записи сверху ленты — от первой страницы до стыка. */
  items: IInsightFeedItem[]
  /**
   * Встретился уже загруженный инсайт: свежие записи дописываются сверху,
   * остальное и курсор не трогаем. Иначе (новых больше, чем страниц, или
   * лента была пуста) лента заменяется этими записями и курсором.
   */
  reachedKnown: boolean
  nextCursor: string | null
}

// Только нужная часть стора: полный RootState замкнул бы типы в цикл.
interface RefreshThunkState {
  insights: { items: IInsightFeedItem[] }
}

/**
 * Тихое обновление ленты без сброса загруженного. Сервер отдаёт ленту
 * страницами от новых к старым, поэтому идём по курсору, пока не дойдём
 * до уже загруженного инсайта: иначе при 51 новом инсайте пользователь
 * увидел бы 50 без «Показать ещё». Ошибки не показываются — их покажет
 * плашка готовности сервиса или следующая попытка.
 */
export const refreshInsightsFeed = createAsyncThunk<
  RefreshedFeed,
  { companyId: string },
  { state: RefreshThunkState; rejectValue: string }
>(
  'insights/refreshInsightsFeed',
  async ({ companyId }, { getState, rejectWithValue }) => {
    const known = new Set(
      getState().insights.items.map((item) => item.insight_id)
    )
    const items: IInsightFeedItem[] = []
    let cursor: string | null = null
    try {
      for (let page = 0; page < MAX_REFRESH_PAGES; page += 1) {
        const feed = await fetchInsightsFeed({
          companyId,
          limit: INITIAL_FEED_LIMIT,
          cursor,
        })
        const stop = feed.items.findIndex((item) => known.has(item.insight_id))
        if (stop !== -1) {
          items.push(...feed.items.slice(0, stop))
          return { items, reachedKnown: true, nextCursor: null }
        }
        items.push(...feed.items)
        cursor = feed.next_cursor
        // Пустая лента — стыковаться не с чем; конец ленты — дальше нечего.
        if (known.size === 0 || !cursor) break
      }
      return { items, reachedKnown: false, nextCursor: cursor }
    } catch (error) {
      return rejectWithValue(
        error instanceof Error ? error.message : 'Не удалось обновить ленту'
      )
    }
  }
)
