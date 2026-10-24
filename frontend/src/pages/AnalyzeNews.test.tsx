import { fireEvent, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { analyzeSavedNews, ingestNews } from '@/shared/api/news.api'
import type { ICreatedAnalysis } from '@/store/models/IInsight'
import type { IIngestedNews } from '@/store/models/INews'
import { setCurrentCompany } from '@/store/reducers/CompanySlice'
import { makeTestStore, renderWithStore } from '@/test/renderWithStore'

import AnalyzeNews from './AnalyzeNews'

vi.mock('@/shared/api/news.api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/shared/api/news.api')>()),
  ingestNews: vi.fn(),
  analyzeSavedNews: vi.fn(),
}))

vi.mock('@/shared/api/insights.api', () => ({
  fetchInsightsFeed: vi
    .fn()
    .mockResolvedValue({ items: [], next_cursor: null }),
}))

// Модель подключена: анализ на экране не выключен демо-режимом.
vi.mock('@/shared/api/system.api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/shared/api/system.api')>()),
  fetchReadiness: vi.fn().mockResolvedValue({
    status: 'ready',
    checks: { rag: true, llm_config: true, database: true },
  }),
}))

// Логину доступны две компании — для блока «Другие компании». Массив один
// и тот же, как у настоящих учёток: селектор не должен отдавать новый.
vi.mock('@/shared/constants/accounts', async (importOriginal) => {
  const companies = ['DEMO-001', 'DEMO-002']
  return {
    ...(await importOriginal<typeof import('@/shared/constants/accounts')>()),
    companiesForLogin: () => companies,
  }
})

vi.mock('@/shared/api/companies.api', () => ({
  fetchCompanyProfile: vi.fn().mockRejectedValue(new Error('нет')),
}))

const saved = { news_id: 42, created: true, duplicate: false, diagnostics: [] }
const created = { insight_id: 7, analysis: { summary: null } }

const fillAndSubmit = () => {
  fireEvent.change(screen.getByPlaceholderText(/Минэнерго/), {
    target: { value: 'Заголовок' },
  })
  fireEvent.change(screen.getByPlaceholderText(/Вставьте текст/), {
    target: { value: 'Текст новости' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Проанализировать' }))
}

const renderPage = () => {
  const store = makeTestStore()
  store.dispatch(setCurrentCompany('DEMO-001'))
  return { store, ...renderWithStore(<AnalyzeNews />, { store }) }
}

describe('AnalyzeNews', () => {
  beforeEach(() => {
    vi.mocked(ingestNews)
      .mockReset()
      .mockResolvedValue(saved as IIngestedNews)
    // Анализ «идёт» до конца теста, если тест не скажет иначе.
    vi.mocked(analyzeSavedNews)
      .mockReset()
      .mockReturnValue(new Promise(() => {}))
  })

  it('пока анализ идёт, «Очистить» заблокирована', async () => {
    renderPage()

    fillAndSubmit()

    expect(screen.getByRole('button', { name: 'Очистить' })).toBeDisabled()
    expect(
      await screen.findByRole('button', { name: 'Анализируем…' })
    ).toBeDisabled()
  })

  it('уход со страницы и возврат не дают запустить второй анализ', async () => {
    const { store, unmount } = renderPage()
    fillAndSubmit()
    await screen.findByText('Анализируем новость')
    unmount()

    renderWithStore(<AnalyzeNews />, { store })

    expect(screen.getByText('Анализируем новость')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Анализируем…' })).toBeDisabled()
    expect(ingestNews).toHaveBeenCalledTimes(1)
  })

  it('готовую новость можно разобрать для другой компании логина', async () => {
    vi.mocked(analyzeSavedNews).mockResolvedValue(
      created as unknown as ICreatedAnalysis
    )
    renderPage()

    fillAndSubmit()
    await screen.findByText('Инсайт готов')
    const others = screen
      .getByText('Другие компании вашего логина')
      .closest('div.border-t') as HTMLElement
    fireEvent.click(
      within(others).getByRole('button', { name: /Проанализировать/ })
    )

    // Модель подключена — новость обычная, без синтетической маркировки.
    expect(ingestNews).toHaveBeenCalledWith(
      expect.not.objectContaining({ source_name: 'synthetic-demo' })
    )
    expect(analyzeSavedNews).toHaveBeenLastCalledWith('DEMO-002', 42)
    // Новость уже в базе — второй раз её не сохраняем.
    expect(ingestNews).toHaveBeenCalledTimes(1)
  })
})
