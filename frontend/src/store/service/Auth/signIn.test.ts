import { describe, expect, it } from 'vitest'

import { parseDemoAccounts } from '@/shared/constants/accounts'
import { reducer } from '@/store/rootReducer'
import { makeTestStore } from '@/test/renderWithStore'

import { signIn } from './signIn'

const accounts = parseDemoAccounts('group=U_1,U_2;fuel=U_3')

const storeWithCompany = (currentCompanyId: string | null) => {
  const initial = reducer(undefined, { type: '@@init' })
  return makeTestStore({
    company: { ...initial.company, currentCompanyId },
  })
}

describe('signIn', () => {
  it('входит и выбирает первую компанию логина вместо чужой', () => {
    const store = storeWithCompany('U_9')

    expect(store.dispatch(signIn('Fuel', accounts))).toBe(true)
    expect(store.getState().auth).toMatchObject({
      isAuthenticated: true,
      username: 'Fuel',
    })
    expect(store.getState().company.currentCompanyId).toBe('U_3')
  })

  it('оставляет выбранную компанию, если она доступна логину', () => {
    const store = storeWithCompany('U_2')

    store.dispatch(signIn('group', accounts))

    expect(store.getState().company.currentCompanyId).toBe('U_2')
  })

  it('неизвестный логин не входит', () => {
    const store = storeWithCompany('U_1')

    expect(store.dispatch(signIn('guest', accounts))).toBe(false)
    expect(store.getState().auth.isAuthenticated).toBe(false)
  })
})
