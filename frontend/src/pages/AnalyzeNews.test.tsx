import { fireEvent, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createAnalysis } from '@/shared/api/insights.api'
import { setCurrentCompany } from '@/store/reducers/CompanySlice'
import { makeTestStore, renderWithStore } from '@/test/renderWithStore'

import AnalyzeNews from './AnalyzeNews'

vi.mock('@/shared/api/insights.api', () => ({
  createAnalysis: vi.fn(),
  fetchInsightsFeed: vi.fn(),
}))

const fillAndSubmit = () => {
  fireEvent.change(screen.getByPlaceholderText(/Минэнерго/), {
    target: { value: 'Заголовок' },
  })
  fireEvent.change(screen.getByPlaceholderText(/Вставьте текст/), {
    target: { value: 'Текст новости' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Проанализировать' }))
}

describe('AnalyzeNews', () => {
  beforeEach(() => {
    // Анализ «идёт» до конца теста.
    vi.mocked(createAnalysis)
      .mockReset()
      .mockReturnValue(new Promise(() => {}))
  })

  it('пока анализ идёт, «Очистить» заблокирована', () => {
    const store = makeTestStore()
    store.dispatch(setCurrentCompany('DEMO-001'))
    renderWithStore(<AnalyzeNews />, { store })

    fillAndSubmit()

    expect(screen.getByRole('button', { name: 'Очистить' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Анализируем…' })).toBeDisabled()
  })

  it('уход со страницы и возврат не дают запустить второй анализ', () => {
    const store = makeTestStore()
    store.dispatch(setCurrentCompany('DEMO-001'))
    const first = renderWithStore(<AnalyzeNews />, { store })
    fillAndSubmit()
    first.unmount()

    renderWithStore(<AnalyzeNews />, { store })

    expect(screen.getByText('Анализируем новость')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Анализируем…' })).toBeDisabled()
    expect(createAnalysis).toHaveBeenCalledTimes(1)
  })
})
