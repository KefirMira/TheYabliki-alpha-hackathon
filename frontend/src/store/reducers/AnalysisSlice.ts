import { type PayloadAction, createSlice } from '@reduxjs/toolkit'

import type { ICreatedAnalysis } from '../models/IInsight'
import { runAnalysis } from '../service/Insights/runAnalysis'

/** Последний анализ своей новости по компании. */
export type AnalysisRun =
  | { status: 'running'; title: string }
  | { status: 'done'; title: string; result: ICreatedAnalysis }
  | { status: 'error'; title: string; message: string; demo: boolean }

export interface AnalysisState {
  /**
   * По компаниям, а не на странице: уход со страницы или смена компании не
   * должны открывать дорогу второму запуску, пока первый ещё идёт.
   */
  byCompany: Record<string, AnalysisRun>
}

const initialState: AnalysisState = {
  byCompany: {},
}

const analysisSlice = createSlice({
  name: 'analysis',
  initialState,
  reducers: {
    /** «Очистить» — забыть результат. Идущий анализ не сбрасывается. */
    clearAnalysis: (state, action: PayloadAction<string>) => {
      if (state.byCompany[action.payload]?.status === 'running') return
      delete state.byCompany[action.payload]
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(runAnalysis.pending, (state, action) => {
        const { companyId, title } = action.meta.arg
        state.byCompany[companyId] = { status: 'running', title }
      })
      .addCase(runAnalysis.fulfilled, (state, action) => {
        const { companyId, title } = action.meta.arg
        state.byCompany[companyId] = {
          status: 'done',
          title,
          result: action.payload,
        }
      })
      .addCase(runAnalysis.rejected, (state, action) => {
        const { companyId, title } = action.meta.arg
        state.byCompany[companyId] = {
          status: 'error',
          title,
          message:
            action.payload?.message ?? 'Не удалось проанализировать новость',
          demo: action.payload?.demo ?? false,
        }
      })
  },
})

export const { clearAnalysis } = analysisSlice.actions
export default analysisSlice.reducer
