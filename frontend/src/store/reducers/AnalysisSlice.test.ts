import { configureStore } from '@reduxjs/toolkit'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchInsightsFeed } from '@/shared/api/insights.api'
import {
  analyzeSavedNews,
  ingestNews,
  type NewsFormValues,
  newsKeyOf,
} from '@/shared/api/news.api'
import { ApiError } from '@/shared/api/request'
import { reducer } from '@/store/rootReducer'

import type { ICreatedAnalysis } from '../models/IInsight'
import type { IIngestedNews } from '../models/INews'
import { runAnalysis } from '../service/Insights/runAnalysis'
import { clearAnalysis } from './AnalysisSlice'
import { setCurrentCompany } from './CompanySlice'

vi.mock('@/shared/api/insights.api', () => ({
  fetchInsightsFeed: vi.fn(),
}))

vi.mock('@/shared/api/news.api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/shared/api/news.api')>()),
  ingestNews: vi.fn(),
  analyzeSavedNews: vi.fn(),
}))

const created = {
  insight_id: 7,
  analysis: { summary: null },
} as unknown as ICreatedAnalysis

const saved = (patch: Partial<IIngestedNews> = {}) =>
  ({
    news_id: 42,
    created: true,
    duplicate: false,
    diagnostics: [],
    ...patch,
  }) as IIngestedNews

const FORM: NewsFormValues = {
  title: 'Заголовок',
  content: 'Текст',
  url: '',
  publishedAt: '',
  synthetic: true,
}

const fromForm = (companyId = 'DEMO-001') => ({
  companyId,
  title: 'Заголовок',
  form: FORM,
  newsKey: newsKeyOf(FORM),
})

const fromSaved = (companyId: string, newsId = 42) => ({
  companyId,
  title: 'Заголовок',
  newsId,
  newsKey: newsKeyOf(FORM),
})

/** Ответ, который приходит, когда тест скажет. */
const deferred = <T>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

const makeStore = (companyId = 'DEMO-001') => {
  const store = configureStore({ reducer })
  store.dispatch(setCurrentCompany(companyId))
  return store
}

describe('AnalysisSlice', () => {
  beforeEach(() => {
    vi.mocked(ingestNews).mockReset().mockResolvedValue(saved())
    vi.mocked(analyzeSavedNews).mockReset()
    vi.mocked(fetchInsightsFeed)
      .mockReset()
      .mockResolvedValue({ items: [], next_cursor: null })
  })

  it('сохраняет новость, потом анализирует её по news_id', async () => {
    vi.mocked(analyzeSavedNews).mockResolvedValue(created)
    const store = makeStore()

    await store.dispatch(runAnalysis(fromForm()))

    expect(ingestNews).toHaveBeenCalledTimes(1)
    expect(analyzeSavedNews).toHaveBeenCalledWith('DEMO-001', 42)
    expect(store.getState().analysis.byCompany['DEMO-001']).toMatchObject({
      status: 'done',
      newsId: 42,
      duplicate: false,
    })
  })

  it('показывает этап: сначала сохранение, затем анализ', async () => {
    const saving = deferred<IIngestedNews>()
    vi.mocked(ingestNews).mockReturnValue(saving.promise)
    vi.mocked(analyzeSavedNews).mockReturnValue(new Promise(() => {}))
    const store = makeStore()

    store.dispatch(runAnalysis(fromForm()))
    expect(store.getState().analysis.byCompany['DEMO-001']).toMatchObject({
      status: 'running',
      stage: 'saving',
    })

    saving.resolve(saved())
    await saving.promise
    await Promise.resolve()
    expect(store.getState().analysis.byCompany['DEMO-001']).toMatchObject({
      status: 'running',
      stage: 'analyzing',
      newsId: 42,
    })
  })

  it('пока анализ идёт, второй запуск для компании не отправляется', () => {
    vi.mocked(analyzeSavedNews).mockReturnValue(new Promise(() => {}))
    const store = makeStore()

    store.dispatch(runAnalysis(fromForm()))
    store.dispatch(clearAnalysis('DEMO-001'))
    store.dispatch(runAnalysis(fromForm()))

    expect(ingestNews).toHaveBeenCalledTimes(1)
    expect(store.getState().analysis.byCompany['DEMO-001'].status).toBe(
      'running'
    )
  })

  it('после ошибки анализа помнит сохранённую новость', async () => {
    vi.mocked(analyzeSavedNews).mockRejectedValue(
      new ApiError('Попытки закончились', 409, 'ANALYSIS_ATTEMPT_LIMIT_REACHED')
    )
    const store = makeStore()

    await store.dispatch(runAnalysis(fromForm()))

    expect(store.getState().analysis.byCompany['DEMO-001']).toMatchObject({
      status: 'error',
      newsId: 42,
      demo: false,
    })
  })

  it('сохранённая новость для другой компании не сохраняется заново', async () => {
    vi.mocked(analyzeSavedNews).mockResolvedValue(created)
    const store = makeStore('DEMO-001')

    await store.dispatch(runAnalysis(fromSaved('DEMO-002')))

    expect(ingestNews).not.toHaveBeenCalled()
    expect(analyzeSavedNews).toHaveBeenCalledWith('DEMO-002', 42)
    // Ленту другой компании не обновляем — её загрузят при переключении.
    expect(fetchInsightsFeed).not.toHaveBeenCalled()
  })

  it('демо-режим бэкенда — отдельная ошибка', async () => {
    vi.mocked(analyzeSavedNews).mockRejectedValue(
      new ApiError('Анализ выключен', 503, 'AI_DISABLED_IN_DEMO')
    )
    const store = makeStore()

    await store.dispatch(runAnalysis(fromForm()))

    expect(analyzeSavedNews).toHaveBeenCalledTimes(1)
    expect(store.getState().analysis.byCompany['DEMO-001']).toMatchObject({
      status: 'error',
      demo: true,
    })
  })

  it('«Очистить» после завершения забывает результат', async () => {
    vi.mocked(analyzeSavedNews).mockResolvedValue(created)
    const store = makeStore()

    await store.dispatch(runAnalysis(fromForm()))
    store.dispatch(clearAnalysis('DEMO-001'))

    expect(store.getState().analysis.byCompany['DEMO-001']).toBeUndefined()
  })
})
