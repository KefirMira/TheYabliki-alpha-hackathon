import { act, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { apiRequest } from '@/shared/api/request'
import { useCompanyCapabilities } from './useCompanyCapabilities'
import { login } from '@/store/reducers/AuthSlice'
import { makeTestStore, renderWithStore } from '@/test/renderWithStore'
vi.mock('@/shared/api/request', () => ({ apiRequest: vi.fn() }))
const View = () => <span>{useCompanyCapabilities('DEMO-001').state}</span>
describe('capability actor scope', () => {
  it('does not reuse AVAILABLE from the previous actor', async () => {
    vi.mocked(apiRequest)
      .mockResolvedValueOnce({
        company_id: 'DEMO-001',
        mode: 'full',
        operations: { analyze_new: { state: 'AVAILABLE', reasons: [] } },
      })
      .mockImplementationOnce(() => new Promise(() => {}))
    const store = makeTestStore()
    const actor = (user_id: string) => ({
      user_id,
      login: user_id,
      companies: [{ source_id: 'DEMO-001', name: null, can_analyze: true }],
    })
    store.dispatch(login(actor('actor-a')))
    renderWithStore(<View />, { store })
    expect(await screen.findByText('AVAILABLE')).toBeInTheDocument()
    act(() => {
      store.dispatch(login(actor('actor-b')))
    })
    expect(screen.getByText('UNKNOWN')).toBeInTheDocument()
  })
})
