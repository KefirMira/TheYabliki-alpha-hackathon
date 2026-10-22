import { createSlice } from '@reduxjs/toolkit'

import type { IInsightFeedItem } from '../models/IInsight'
import { getInsightsFeed } from '../service/Insights/getInsightsFeed'
import { setCurrentCompany } from './CompanySlice'

export interface InsightsState {
  /** Компания, чья лента сейчас в состоянии. */
  companyId: string | null
  items: IInsightFeedItem[]
  nextCursor: string | null
  /** Загрузка первой страницы. */
  loadingList: boolean
  /** Догрузка следующей страницы по курсору. */
  loadingMore: boolean
  error: string | undefined
  errorMore: string | undefined
  isInitialized: boolean
  /**
   * Последний запрос ленты. Ответ другого запроса (например, прежней
   * компании, пока пользователь её переключал) в стор не пишется.
   */
  requestId: string | null
}

const initialState: InsightsState = {
  companyId: null,
  items: [],
  nextCursor: null,
  loadingList: false,
  loadingMore: false,
  error: undefined,
  errorMore: undefined,
  isInitialized: false,
  requestId: null,
}

const insightsSlice = createSlice({
  name: 'insights',
  initialState,
  reducers: {
    resetInsightsFeed: () => initialState,
  },
  extraReducers: (builder) => {
    // Свой ответ — ответ последнего запроса и по ленте той же компании.
    const isCurrent = (
      state: InsightsState,
      meta: { requestId: string; arg: { companyId: string } }
    ) =>
      meta.requestId === state.requestId &&
      meta.arg.companyId === state.companyId

    builder
      // Смена компании обнуляет ленту и забывает её запрос: ответ прежней
      // компании может прийти раньше, чем лента новой начнёт грузиться.
      .addCase(setCurrentCompany, () => initialState)
      .addCase(getInsightsFeed.pending, (state, action) => {
        const { companyId, cursor } = action.meta.arg
        state.requestId = action.meta.requestId
        if (cursor) {
          state.loadingMore = true
          state.errorMore = undefined
          return
        }
        // Первая страница: лента начинается заново.
        state.companyId = companyId
        state.items = []
        state.nextCursor = null
        state.loadingList = true
        state.loadingMore = false
        state.error = undefined
        state.errorMore = undefined
        state.isInitialized = false
      })
      .addCase(getInsightsFeed.fulfilled, (state, action) => {
        if (!isCurrent(state, action.meta)) return
        const { items, next_cursor } = action.payload
        if (action.meta.arg.cursor) {
          // Курсор фиксирует позицию, но повтор строки на стыке страниц
          // не должен дать дубль карточки.
          const known = new Set(state.items.map((item) => item.insight_id))
          state.items.push(...items.filter((i) => !known.has(i.insight_id)))
        } else {
          state.items = items
        }
        state.nextCursor = next_cursor
        state.loadingList = false
        state.loadingMore = false
        state.isInitialized = true
      })
      .addCase(getInsightsFeed.rejected, (state, action) => {
        if (!isCurrent(state, action.meta)) return
        const message = action.payload ?? 'Не удалось загрузить ленту'
        if (action.meta.arg.cursor) {
          state.loadingMore = false
          state.errorMore = message
          return
        }
        state.loadingList = false
        state.error = message
        state.isInitialized = true
      })
  },
})

export const { resetInsightsFeed } = insightsSlice.actions
export default insightsSlice.reducer
