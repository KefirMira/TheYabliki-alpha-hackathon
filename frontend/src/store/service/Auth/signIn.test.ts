import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import {
  accessToken,
  clearSession,
  setAccessToken,
} from '@/shared/auth/session'
import { apiRequest } from '@/shared/api/request'
import { login } from '@/store/reducers/AuthSlice'
import { setCurrentCompany } from '@/store/reducers/CompanySlice'
import { getCompanyProfile } from '@/store/service/Company/getCompanyProfile'
import { makeTestStore } from '@/test/renderWithStore'
import { signIn, signOut, restoreSession } from './signIn'
const user = {
  user_id: 'synthetic-user-a',
  login: 'synthetic-demo-a',
  companies: [
    { source_id: 'DEMO-001', name: 'Synthetic A', can_analyze: false },
  ],
}
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
beforeEach(() => {
  sessionStorage.clear()
  localStorage.clear()
  clearSession()
})
afterEach(() => {
  clearSession()
  vi.unstubAllGlobals()
})
describe('server authentication', () => {
  it('checks credentials and takes company access exclusively from me', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        json({
          access_token: 'synthetic-token',
          token_type: 'bearer',
          expires_in: 3600,
        })
      )
      .mockResolvedValueOnce(json(user))
    vi.stubGlobal('fetch', fetcher)
    const store = makeTestStore()
    store.dispatch(setCurrentCompany('FOREIGN'))
    await store.dispatch(signIn('synthetic-demo-a', 'synthetic-password'))
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({
      login: 'synthetic-demo-a',
      password: 'synthetic-password',
    })
    expect(fetcher.mock.calls[1][1].headers.Authorization).toBe(
      'Bearer synthetic-token'
    )
    expect(store.getState().auth.userId).toBe(user.user_id)
    expect(store.getState().company.currentCompanyId).toBe('DEMO-001')
  })
  it('rejects wrong passwords without a local fallback', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          json({ detail: { code: 'INVALID_CREDENTIALS' } }, 401)
        )
    )
    const store = makeTestStore()
    await expect(store.dispatch(signIn('expert', 'wrong'))).rejects.toThrow(
      'Неверный логин или пароль'
    )
    expect(store.getState().auth.isAuthenticated).toBe(false)
    expect(accessToken()).toBeNull()
  })
  it('restores a token only after server validation and clears expired sessions', async () => {
    setAccessToken('synthetic-token')
    const store = makeTestStore()
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(json(user))
        .mockResolvedValueOnce(
          json({ detail: { code: 'AUTHENTICATION_REQUIRED' } }, 401)
        )
    )
    await store.dispatch(restoreSession())
    expect(store.getState().auth.isAuthenticated).toBe(true)
    await store.dispatch(restoreSession())
    expect(store.getState().auth.isAuthenticated).toBe(false)
    expect(store.getState().company.currentCompanyId).toBeNull()
    expect(accessToken()).toBeNull()
  })
  it('revokes server session, accepts empty 204 and removes protected data', async () => {
    setAccessToken('synthetic-token')
    const store = makeTestStore()
    store.dispatch(login(user))
    store.dispatch(setCurrentCompany('DEMO-001'))
    const fetcher = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetcher)
    await store.dispatch(signOut())
    expect(fetcher.mock.calls[0][0]).toContain('/api/auth/logout')
    expect(fetcher.mock.calls[0][1].headers.Authorization).toBe(
      'Bearer synthetic-token'
    )
    expect(accessToken()).toBeNull()
    expect(store.getState().auth.isAuthenticated).toBe(false)
    expect(store.getState().company.currentCompanyId).toBeNull()
    expect(store.getState().insights.items).toEqual([])
  })
  it('does not pretend server logout succeeded after a network failure', async () => {
    setAccessToken('synthetic-token')
    const store = makeTestStore()
    store.dispatch(login(user))
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network')))
    await expect(store.dispatch(signOut())).rejects.toThrow()
    expect(store.getState().auth.isAuthenticated).toBe(true)
    expect(accessToken()).toBe('synthetic-token')
  })
  it('discards an old response without expiring the new session', async () => {
    let resolve!: (response: Response) => void
    vi.stubGlobal(
      'fetch',
      vi.fn().mockReturnValue(
        new Promise<Response>((r) => {
          resolve = r
        })
      )
    )
    setAccessToken('old-token')
    const request = apiRequest('/api/me', { method: 'GET' }, 'failed')
    setAccessToken('new-token')
    resolve(json({ detail: { code: 'AUTHENTICATION_REQUIRED' } }, 401))
    await expect(request).rejects.toMatchObject({ code: 'SESSION_CHANGED' })
    expect(accessToken()).toBe('new-token')
  })
  it('drops late thunk results after logout/new login', () => {
    const store = makeTestStore()
    setAccessToken('old-token')
    store.dispatch(login(user))
    store.dispatch(setCurrentCompany('DEMO-001'))
    store.dispatch(getCompanyProfile.pending('old-request', 'DEMO-001'))
    setAccessToken('new-token')
    store.dispatch(
      login({ ...user, user_id: 'synthetic-user-b', login: 'synthetic-demo-b' })
    )
    store.dispatch(setCurrentCompany('DEMO-001'))
    store.dispatch(
      getCompanyProfile.fulfilled(
        {
          company_id: 'DEMO-001',
          name: 'PRIVATE OLD',
          name_is_placeholder: false,
          industry: null,
          region: null,
          revenue: null,
          revenue_year: null,
          client_status: null,
          credit_exposure: null,
        },
        'old-request',
        'DEMO-001'
      )
    )
    expect(store.getState().company.profile).toBeNull()
  })
})
