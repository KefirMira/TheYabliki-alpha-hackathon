import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { reducer } from '@/store/rootReducer'
import { makeTestStore, renderWithStore } from '@/test/renderWithStore'

import Insights from './Insights'
import PulseSummary from './PulseSummary'

// Сборка без VITE_DEMO_COMPANY_IDS: компании нет, запрос ленты не уходит.
const noCompanyStore = () => {
  const initial = reducer(undefined, { type: '@@init' })
  return makeTestStore({
    company: { ...initial.company, currentCompanyId: null },
  })
}

describe('экраны ленты без компании', () => {
  it('лента показывает «Компания не выбрана», а не вечную загрузку', () => {
    renderWithStore(<Insights />, { store: noCompanyStore() })

    expect(screen.getByText('Компания не выбрана')).toBeInTheDocument()
    expect(document.querySelector('[aria-busy="true"]')).toBeNull()
  })

  it('сводка показывает «Компания не выбрана»', () => {
    renderWithStore(<PulseSummary />, { store: noCompanyStore() })

    expect(screen.getByText('Компания не выбрана')).toBeInTheDocument()
  })
})
