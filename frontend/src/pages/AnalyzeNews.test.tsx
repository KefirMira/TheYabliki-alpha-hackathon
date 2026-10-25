import { act, fireEvent, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { analyzeSavedNews, ingestNews } from '@/shared/api/news.api'
import type { ICreatedAnalysis } from '@/store/models/IInsight'
import type { IIngestedNews } from '@/store/models/INews'
import { login } from '@/store/reducers/AuthSlice'
import { setCurrentCompany } from '@/store/reducers/CompanySlice'
import { makeTestStore, renderWithStore } from '@/test/renderWithStore'

import AnalyzeNews from './AnalyzeNews'
import { useCompanyCapabilities } from '@/hooks/useCompanyCapabilities'
vi.mock('@/hooks/useCompanyCapabilities', () => ({
  useCompanyCapabilities: vi
    .fn()
    .mockReturnValue({ blocked: false, state: 'AVAILABLE', reasons: [] }),
}))

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

const renderPage = async () => {
  const store = makeTestStore()
  store.dispatch(
    login({
      user_id: 'synthetic-user',
      login: 'synthetic-demo-a',
      companies: ['DEMO-001', 'DEMO-002'].map((source_id) => ({
        source_id,
        name: null,
        can_analyze: true,
      })),
    })
  )
  store.dispatch(setCurrentCompany('DEMO-001'))
  const rendered = renderWithStore(<AnalyzeNews />, { store })
  await act(async () => {})
  return { store, ...rendered }
}

describe('AnalyzeNews', () => {
  beforeEach(() => {
    vi.mocked(useCompanyCapabilities).mockReturnValue({
      blocked: false,
      state: 'AVAILABLE',
      reasons: [],
    })
    vi.mocked(ingestNews)
      .mockReset()
      .mockResolvedValue(saved as IIngestedNews)
    // Анализ «идёт» до конца теста, если тест не скажет иначе.
    vi.mocked(analyzeSavedNews)
      .mockReset()
      .mockReturnValue(new Promise(() => {}))
  })

  it('пока анализ идёт, «Очистить» заблокирована', async () => {
    await renderPage()

    await act(async () => {
      fillAndSubmit()
    })

    expect(screen.getByRole('button', { name: 'Очистить' })).toBeDisabled()
    expect(
      await screen.findByRole('button', { name: 'Анализируем…' })
    ).toBeDisabled()
  })

  it('уход со страницы и возврат не дают запустить второй анализ', async () => {
    const { store, unmount } = await renderPage()
    await act(async () => {
      fillAndSubmit()
    })
    await screen.findByText('Анализируем новость')
    unmount()

    await act(async () => {
      renderWithStore(<AnalyzeNews />, { store })
    })

    expect(screen.getByText('Анализируем новость')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Анализируем…' })).toBeDisabled()
    expect(ingestNews).toHaveBeenCalledTimes(1)
  })

  it('готовую новость можно разобрать для другой компании логина', async () => {
    vi.mocked(analyzeSavedNews).mockResolvedValue(
      created as unknown as ICreatedAnalysis
    )
    await renderPage()

    await act(async () => {
      fillAndSubmit()
    })
    await screen.findByText('Инсайт готов')
    const others = screen
      .getByText('Другие компании вашего логина')
      .closest('div.border-t') as HTMLElement
    await act(async () => {
      fireEvent.click(
        within(others).getByRole('button', { name: /Проанализировать/ })
      )
    })

    // Модель подключена — новость обычная, без синтетической маркировки.
    expect(ingestNews).toHaveBeenCalledWith(
      expect.not.objectContaining({ source_name: 'synthetic-demo' })
    )
    expect(analyzeSavedNews).toHaveBeenLastCalledWith('DEMO-002', 42)
    // Новость уже в базе — второй раз её не сохраняем.
    expect(ingestNews).toHaveBeenCalledTimes(1)
  })
})

it('blocks AI despite llm_config when company capability is BLOCKED', async () => {
  vi.mocked(ingestNews).mockClear()
  vi.mocked(useCompanyCapabilities).mockReturnValue({
    blocked: true,
    state: 'BLOCKED',
    reasons: ['COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED'],
  })
  await renderPage()
  expect(
    screen.getByRole('button', { name: 'Проанализировать' })
  ).toBeDisabled()
  expect(ingestNews).not.toHaveBeenCalled()
})

it('dataset требует подтверждения и выбирает отдельный endpoint', async () => {
  vi.mocked(ingestNews)
    .mockReset()
    .mockResolvedValue(saved as IIngestedNews)
  vi.mocked(analyzeSavedNews)
    .mockReset()
    .mockReturnValue(new Promise(() => {}))
  vi.mocked(useCompanyCapabilities).mockReturnValue({
    blocked: false,
    state: 'AVAILABLE',
    reasons: [],
    dataset: true,
    datasetTransport: 'fake',
  })
  await renderPage()
  expect(screen.getByText('Локальная проверка без LLM')).toBeInTheDocument()
  await act(async () => {
    fillAndSubmit()
  })
  expect(ingestNews).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('checkbox'))
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Проанализировать' }))
  })
  expect(analyzeSavedNews).toHaveBeenCalledWith('DEMO-001', 42, true)
})
