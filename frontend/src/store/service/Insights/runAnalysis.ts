import { createAsyncThunk } from '@reduxjs/toolkit'

import { createAnalysis } from '@/shared/api/insights.api'
import { ApiError } from '@/shared/api/request'
import { INITIAL_FEED_LIMIT } from '@/shared/constants/insights'
import type { ICreatedAnalysis } from '@/store/models/IInsight'
import type { AnalysisState } from '@/store/reducers/AnalysisSlice'

import { getInsightsFeed } from './getInsightsFeed'

export interface RunAnalysisArgs {
  companyId: string
  title: string
  text: string
}

export interface RunAnalysisError {
  message: string
  /** Бэкенд в демо-режиме: анализ выключен, это не сбой. */
  demo: boolean
}

// Только нужная часть стора: полный RootState замкнул бы типы в цикл.
interface AnalysisThunkState {
  analysis: AnalysisState
  company: { currentCompanyId: string | null }
}

/**
 * Анализ своей новости: `POST /analyses`. Запрос не идемпотентен — каждый
 * вызов это новый запуск LLM, поэтому второй запуск для компании, пока
 * идёт первый, не отправляется (`condition`). Повторов при ошибке нет.
 */
export const runAnalysis = createAsyncThunk<
  ICreatedAnalysis,
  RunAnalysisArgs,
  { state: AnalysisThunkState; rejectValue: RunAnalysisError }
>(
  'analysis/run',
  async (
    { companyId, title, text },
    { dispatch, getState, rejectWithValue }
  ) => {
    try {
      const result = await createAnalysis(companyId, { title, text })
      // Новый инсайт — в ленту без перезагрузки. Ленту другой компании не
      // трогаем: запрос первой страницы сбросил бы ленту выбранной.
      if (getState().company.currentCompanyId === companyId) {
        dispatch(getInsightsFeed({ companyId, limit: INITIAL_FEED_LIMIT }))
      }
      return result
    } catch (error) {
      return rejectWithValue({
        message:
          error instanceof Error
            ? error.message
            : 'Не удалось проанализировать новость',
        demo: error instanceof ApiError && error.code === 'AI_DISABLED_IN_DEMO',
      })
    }
  },
  {
    condition: ({ companyId }, { getState }) =>
      getState().analysis.byCompany[companyId]?.status !== 'running',
  }
)
