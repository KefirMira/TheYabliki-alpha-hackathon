import { type PayloadAction, createSlice } from '@reduxjs/toolkit'

import type { ICreatedAnalysis } from '../models/IInsight'
import type { NewsDiagnostic } from '../models/INews'
import { analysisNewsSaved, runAnalysis } from '../service/Insights/runAnalysis'

interface RunBase {
  title: string
  /** Новость в базе, когда она уже сохранена. */
  newsId: number | null
  /**
   * Отпечаток содержимого формы: повторная отправка той же новости берёт
   * сохранённый newsId и не сохраняет её снова.
   */
  newsKey: string
}

/** Последний анализ новости по компании. */
export type AnalysisRun = RunBase &
  (
    | { status: 'running'; stage: 'saving' | 'analyzing' }
    | {
        status: 'done'
        result: ICreatedAnalysis
        duplicate: boolean
        diagnostics: NewsDiagnostic[]
      }
    | { status: 'error'; message: string; demo: boolean }
  )

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
        const { companyId, title, newsKey } = action.meta.arg
        const newsId =
          'newsId' in action.meta.arg ? action.meta.arg.newsId : null
        state.byCompany[companyId] = {
          status: 'running',
          stage: newsId === null ? 'saving' : 'analyzing',
          title,
          newsId,
          newsKey,
        }
      })
      .addCase(analysisNewsSaved, (state, action) => {
        const run = state.byCompany[action.payload.companyId]
        if (run?.status !== 'running') return
        run.stage = 'analyzing'
        run.newsId = action.payload.newsId
      })
      .addCase(runAnalysis.fulfilled, (state, action) => {
        const { companyId, title, newsKey } = action.meta.arg
        const { result, newsId, duplicate, diagnostics } = action.payload
        state.byCompany[companyId] = {
          status: 'done',
          title,
          newsId,
          newsKey,
          result,
          duplicate,
          diagnostics,
        }
      })
      .addCase(runAnalysis.rejected, (state, action) => {
        const { companyId, title, newsKey } = action.meta.arg
        state.byCompany[companyId] = {
          status: 'error',
          title,
          newsKey,
          newsId: action.payload?.newsId ?? null,
          message:
            action.payload?.message ?? 'Не удалось проанализировать новость',
          demo: action.payload?.demo ?? false,
        }
      })
  },
})

export const { clearAnalysis } = analysisSlice.actions
export default analysisSlice.reducer
