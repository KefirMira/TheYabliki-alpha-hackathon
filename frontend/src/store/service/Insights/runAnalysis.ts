import { createAction, createAsyncThunk } from '@reduxjs/toolkit'

import {
  analyzeSavedNews,
  ingestNews,
  type NewsFormValues,
  newsPayload,
} from '@/shared/api/news.api'
import { ApiError } from '@/shared/api/request'
import type {
  ICreatedAnalysis,
  IInsightFeedItem,
} from '@/store/models/IInsight'
import type { NewsDiagnostic } from '@/store/models/INews'
import type { AnalysisState } from '@/store/reducers/AnalysisSlice'

import { refreshInsightsFeed } from './refreshInsightsFeed'

/**
 * Что анализировать: новость из формы (сначала сохраняется в базу) или уже
 * сохранённую — повтор после ошибки и анализ той же новости для другой
 * компании логина.
 */
export type RunAnalysisArgs = { companyId: string; title: string } & (
  | { form: NewsFormValues; newsKey: string }
  | { newsId: number; newsKey: string }
)

export interface RunAnalysisResult {
  result: ICreatedAnalysis
  newsId: number
  /** Такая новость уже была в базе — сохранённая не перезаписана. */
  duplicate: boolean
  diagnostics: NewsDiagnostic[]
}

export interface RunAnalysisError {
  message: string
  /** Бэкенд в демо-режиме: анализ выключен, это не сбой. */
  demo: boolean
  /** Новость успела сохраниться — повтор не создаст её заново. */
  newsId: number | null
}

/** Новость сохранена, начался анализ — для прогресса на экране. */
export const analysisNewsSaved = createAction<{
  companyId: string
  newsId: number
}>('analysis/newsSaved')

// Только нужная часть стора: полный RootState замкнул бы типы в цикл.
interface AnalysisThunkState {
  analysis: AnalysisState
  company: { currentCompanyId: string | null }
  // Нужна обновлению ленты, которое запускается после анализа.
  insights: { items: IInsightFeedItem[] }
}

/**
 * Анализ новости для компании в два шага: `POST /api/news` (без ИИ, дубль
 * той же новости не создаётся) и `POST .../news/{news_id}/analyses`
 * (готовая пара «компания + новость» возвращается без повторного вызова
 * LLM). Второй запуск для компании, пока идёт первый, не отправляется
 * (`condition`). Автоповторов нет.
 */
export const runAnalysis = createAsyncThunk<
  RunAnalysisResult,
  RunAnalysisArgs,
  { state: AnalysisThunkState; rejectValue: RunAnalysisError }
>(
  'analysis/run',
  async (args, { dispatch, getState, rejectWithValue }) => {
    const { companyId } = args
    let newsId = 'newsId' in args ? args.newsId : null
    let duplicate = false
    let diagnostics: NewsDiagnostic[] = []
    try {
      if ('form' in args) {
        const saved = await ingestNews(newsPayload(args.form))
        newsId = saved.news_id
        duplicate = saved.duplicate
        diagnostics = saved.diagnostics
        dispatch(analysisNewsSaved({ companyId, newsId }))
      }
      const result = await analyzeSavedNews(companyId, newsId!)
      // Новый инсайт — в ленту с пометкой «Новое». Ленту другой компании
      // не трогаем: её загрузят при переключении.
      if (getState().company.currentCompanyId === companyId) {
        dispatch(refreshInsightsFeed({ companyId }))
      }
      return { result, newsId: newsId!, duplicate, diagnostics }
    } catch (error) {
      return rejectWithValue({
        message:
          error instanceof Error
            ? error.message
            : 'Не удалось проанализировать новость',
        demo: error instanceof ApiError && error.code === 'AI_DISABLED_IN_DEMO',
        newsId,
      })
    }
  },
  {
    condition: ({ companyId }, { getState }) =>
      getState().analysis.byCompany[companyId]?.status !== 'running',
  }
)
