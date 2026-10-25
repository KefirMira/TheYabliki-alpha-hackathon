import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useLocation } from 'react-router-dom'
import { login } from '@/store/reducers/AuthSlice'
import { setCurrentCompany } from '@/store/reducers/CompanySlice'
import { makeTestStore, renderWithStore } from '@/test/renderWithStore'
import AlfaHeader from './AlfaHeader'
vi.mock('@/hooks/useCompanyProfiles', () => ({
  useCompanyProfiles: () => ({}),
}))
vi.mock('./NotificationsBell', () => ({ default: () => null }))
const Location = () => <span data-testid="route">{useLocation().pathname}</span>
describe('server company menu', () => {
  it('leaves the old insight route when switching the membership company', async () => {
    const store = makeTestStore()
    store.dispatch(
      login({
        user_id: 'test-user',
        login: 'synthetic',
        companies: ['DEMO-001', 'DEMO-003'].map((source_id) => ({
          source_id,
          name: null,
          can_analyze: true,
        })),
      })
    )
    store.dispatch(setCurrentCompany('DEMO-001'))
    renderWithStore(
      <>
        <AlfaHeader />
        <Location />
      </>,
      { store, initialEntries: ['/pulse/insights/1'] }
    )
    fireEvent.click(screen.getByRole('button', { name: /synthetic/ }))
    fireEvent.click(await screen.findByRole('button', { name: /DEMO-003/ }))
    expect(store.getState().company.currentCompanyId).toBe('DEMO-003')
    expect(screen.getByTestId('route')).toHaveTextContent('/pulse/insights')
    expect(screen.getByTestId('route')).not.toHaveTextContent('/1')
  })
})
