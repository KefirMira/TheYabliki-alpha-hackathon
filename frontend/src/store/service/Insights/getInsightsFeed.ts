import { createAsyncThunk } from '@reduxjs/toolkit'

import {
  type FetchInsightsFeedParams,
  fetchInsightsFeed,
} from '@/shared/api/insights.api'
import type { IInsightFeed } from '@/store/models/IInsight'

/** Страница ленты. Без курсора — первая страница (лента начинается заново). */
export const getInsightsFeed = createAsyncThunk<
  IInsightFeed,
  FetchInsightsFeedParams,
  { rejectValue: string }
>('insights/getInsightsFeed', async (params, { rejectWithValue }) => {
  try {
    return await fetchInsightsFeed(params)
  } catch (error) {
    return rejectWithValue(
      error instanceof Error ? error.message : 'Не удалось загрузить ленту'
    )
  }
})
