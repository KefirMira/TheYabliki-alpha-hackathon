import { type PayloadAction, createSlice } from '@reduxjs/toolkit'

import type { IInsightFeedItem } from '../models/IInsight'
import { getInsightsFeed } from '../service/Insights/getInsightsFeed'
import { refreshInsightsFeed } from '../service/Insights/refreshInsightsFeed'
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
  /** Инсайты, пришедшие при фоновом обновлении и ещё не открытые. */
  newIds: number[]
  /** Когда лента последний раз сверялась с сервером (ISO). */
  refreshedAt: string | null
  /**
   * Когда фоновое обновление последний раз не удалось (ISO). Само оно
   * ошибку не показывает — по этой отметке перепроверяется готовность
   * сервиса, и при сбое появляется плашка.
   */
  refreshFailedAt: string | null
  /**
   * Последнее фоновое или ручное обновление. Ответ более раннего, пришедший
   * позже, устарел: его снимок ленты старше, и замена затёрла бы свежую.
   */
  refreshRequestId: string | null
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
  newIds: [],
  refreshedAt: null,
  refreshFailedAt: null,
  refreshRequestId: null,
}

const insightsSlice = createSlice({
  name: 'insights',
  initialState,
  reducers: {
    resetInsightsFeed: () => initialState,
    /** Инсайт открыли — он больше не «новый». */
    markInsightSeen: (state, action: PayloadAction<number>) => {
      state.newIds = state.newIds.filter((id) => id !== action.payload)
    },
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
        // Первая страница: лента начинается заново, а идущее обновление
        // устарело — его ответ относится к прежней ленте.
        state.refreshRequestId = null
        state.companyId = companyId
        state.items = []
        state.nextCursor = null
        state.loadingList = true
        state.loadingMore = false
        state.error = undefined
        state.errorMore = undefined
        state.isInitialized = false
        state.newIds = []
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
          state.refreshedAt = new Date().toISOString()
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
      // Обновлений может идти несколько (фоновое и «Обновить»): применяется
      // только ответ последнего запущенного.
      .addCase(refreshInsightsFeed.pending, (state, action) => {
        state.refreshRequestId = action.meta.requestId
      })
      // Фоновое обновление не трогает загрузку: устаревший ответ, ответ во
      // время загрузки первой страницы, после ошибки или по другой компании
      // отбрасывается.
      .addCase(refreshInsightsFeed.fulfilled, (state, action) => {
        if (
          action.meta.requestId !== state.refreshRequestId ||
          action.meta.arg.companyId !== state.companyId ||
          !state.isInitialized ||
          state.loadingList ||
          state.error
        ) {
          return
        }
        const { items, reachedKnown, nextCursor } = action.payload
        // Замена ленты во время «Показать ещё» перепутала бы страницы —
        // такой ответ пропускаем, следующее обновление повторит.
        if (!reachedKnown && state.loadingMore) return

        const known = new Set(state.items.map((item) => item.insight_id))
        const fresh = items.filter((item) => !known.has(item.insight_id))
        if (reachedKnown) {
          // Дошли до загруженного: новые сверху, остальное и курсор те же.
          state.items.unshift(...fresh)
        } else {
          // Новых больше, чем догрузили, или лента была пуста: лента —
          // эти страницы, курсор — их продолжение, «Показать ещё» верно.
          state.items = items
          state.nextCursor = nextCursor
          state.errorMore = undefined
        }
        state.newIds.push(...fresh.map((item) => item.insight_id))
        state.refreshedAt = new Date().toISOString()
        state.refreshFailedAt = null
        state.refreshRequestId = null
      })
      .addCase(refreshInsightsFeed.rejected, (state, action) => {
        if (action.meta.requestId !== state.refreshRequestId) return
        state.refreshFailedAt = new Date().toISOString()
        state.refreshRequestId = null
      })
  },
})

export const { resetInsightsFeed, markInsightSeen } = insightsSlice.actions
export default insightsSlice.reducer
