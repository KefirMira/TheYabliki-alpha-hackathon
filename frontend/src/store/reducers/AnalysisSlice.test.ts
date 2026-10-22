import { configureStore } from '@reduxjs/toolkit'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createAnalysis, fetchInsightsFeed } from '@/shared/api/insights.api'
import { ApiError } from '@/shared/api/request'
import { reducer } from '@/store/rootReducer'

import type { ICreatedAnalysis } from '../models/IInsight'
import { runAnalysis } from '../service/Insights/runAnalysis'
import { clearAnalysis } from './AnalysisSlice'
import { setCurrentCompany } from './CompanySlice'

vi.mock('@/shared/api/insights.api', () => ({
  createAnalysis: vi.fn(),
  fetchInsightsFeed: vi.fn(),
}))

const created = {
  insight_id: 7,
  analysis: { summary: null },
} as unknown as ICreatedAnalysis

/** Ответ, который приходит, когда тест скажет. */
const deferred = <T>() => {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const makeStore = (companyId = 'DEMO-001') => {
  const store = configureStore({ reducer })
  store.dispatch(setCurrentCompany(companyId))
  return store
}

const news = (companyId = 'DEMO-001') => ({
  companyId,
  title: 'Заголовок',
  text: 'Текст',
})

describe('AnalysisSlice', () => {
  beforeEach(() => {
    vi.mocked(createAnalysis).mockReset()
    vi.mocked(fetchInsightsFeed)
      .mockReset()
      .mockResolvedValue({ items: [], next_cursor: null })
  })

  it('пока анализ идёт, второй запуск для компании не отправляется', async () => {
    const response = deferred<ICreatedAnalysis>()
    vi.mocked(createAnalysis).mockReturnValue(response.promise)
    const store = makeStore()

    const first = store.dispatch(runAnalysis(news()))
    store.dispatch(runAnalysis(news()))

    expect(createAnalysis).toHaveBeenCalledTimes(1)
    expect(store.getState().analysis.byCompany['DEMO-001'].status).toBe(
      'running'
    )

    response.resolve(created)
    await first
    expect(store.getState().analysis.byCompany['DEMO-001']).toMatchObject({
      status: 'done',
      title: 'Заголовок',
    })
  })

  it('«Очистить» не сбрасывает идущий анализ', () => {
    vi.mocked(createAnalysis).mockReturnValue(new Promise(() => {}))
    const store = makeStore()

    store.dispatch(runAnalysis(news()))
    store.dispatch(clearAnalysis('DEMO-001'))
    store.dispatch(runAnalysis(news()))

    expect(store.getState().analysis.byCompany['DEMO-001'].status).toBe(
      'running'
    )
    expect(createAnalysis).toHaveBeenCalledTimes(1)
  })

  it('после завершения «Очистить» забывает результат', async () => {
    vi.mocked(createAnalysis).mockResolvedValue(created)
    const store = makeStore()

    await store.dispatch(runAnalysis(news()))
    store.dispatch(clearAnalysis('DEMO-001'))

    expect(store.getState().analysis.byCompany['DEMO-001']).toBeUndefined()
  })

  it('анализ другой компании не блокируется', () => {
    vi.mocked(createAnalysis).mockReturnValue(new Promise(() => {}))
    const store = makeStore()

    store.dispatch(runAnalysis(news('DEMO-001')))
    store.dispatch(runAnalysis(news('DEMO-002')))

    expect(createAnalysis).toHaveBeenCalledTimes(2)
  })

  it('демо-режим бэкенда — отдельная ошибка, без повтора запроса', async () => {
    vi.mocked(createAnalysis).mockRejectedValue(
      new ApiError('Анализ выключен', 503, 'AI_DISABLED_IN_DEMO')
    )
    const store = makeStore()

    await store.dispatch(runAnalysis(news()))

    expect(createAnalysis).toHaveBeenCalledTimes(1)
    expect(store.getState().analysis.byCompany['DEMO-001']).toMatchObject({
      status: 'error',
      demo: true,
    })
  })

  it('после анализа лента обновляется только у выбранной компании', async () => {
    const response = deferred<ICreatedAnalysis>()
    vi.mocked(createAnalysis).mockReturnValue(response.promise)
    const store = makeStore('DEMO-001')

    const pending = store.dispatch(runAnalysis(news('DEMO-001')))
    // Пока шёл анализ, пользователь переключился на другую компанию.
    store.dispatch(setCurrentCompany('DEMO-002'))
    response.resolve(created)
    await pending

    expect(fetchInsightsFeed).not.toHaveBeenCalled()
    expect(store.getState().insights.companyId).toBeNull()
  })
})
