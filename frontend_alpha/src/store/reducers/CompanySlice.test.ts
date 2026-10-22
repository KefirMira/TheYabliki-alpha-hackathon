import { describe, expect, it } from 'vitest'

import type { ICompanyProfile } from '../models/ICompany'
import { getCompanyProfile } from '../service/Company/getCompanyProfile'
import reducer, { type CompanyState, setCurrentCompany } from './CompanySlice'

const profile = (companyId: string, name: string): ICompanyProfile => ({
  company_id: companyId,
  name,
  name_is_placeholder: false,
  industry: null,
  region: null,
  revenue: null,
  revenue_year: null,
  client_status: 'CLIENT',
  credit_exposure: null,
})

const run = (...actions: Parameters<typeof reducer>[1][]): CompanyState =>
  actions.reduce(reducer, reducer(undefined, { type: '@@init' }))

// Переключение A → B → A: два запроса профиля A, первый устарел.
const switchBackAndForth = () => [
  setCurrentCompany('A'),
  getCompanyProfile.pending('r1', 'A'),
  setCurrentCompany('B'),
  getCompanyProfile.pending('r2', 'B'),
  setCurrentCompany('A'),
  getCompanyProfile.pending('r3', 'A'),
]

describe('CompanySlice', () => {
  it('запоздавший ответ первого запроса не затирает свежий профиль', () => {
    const state = run(
      ...switchBackAndForth(),
      getCompanyProfile.fulfilled(profile('A', 'Свежий'), 'r3', 'A'),
      getCompanyProfile.fulfilled(profile('A', 'Устаревший'), 'r1', 'A')
    )

    expect(state.profile?.name).toBe('Свежий')
    expect(state.loading).toBe(false)
  })

  it('ошибка устаревшего запроса не появляется после успешной загрузки', () => {
    const state = run(
      ...switchBackAndForth(),
      getCompanyProfile.fulfilled(profile('A', 'Свежий'), 'r3', 'A'),
      getCompanyProfile.rejected(null, 'r1', 'A', 'Сервер недоступен')
    )

    expect(state.error).toBeUndefined()
    expect(state.profile?.name).toBe('Свежий')
  })

  // A → B: ответ A приходит раньше, чем useEffect отправит запрос по B.
  it('ответ прежней компании до запроса новой не попадает в профиль', () => {
    const state = run(
      setCurrentCompany('A'),
      getCompanyProfile.pending('r1', 'A'),
      setCurrentCompany('B'),
      getCompanyProfile.fulfilled(profile('A', 'Компания A'), 'r1', 'A')
    )

    expect(state.currentCompanyId).toBe('B')
    expect(state.profile).toBeNull()
    expect(state.loading).toBe(false)
  })

  it('ошибка прежней компании до запроса новой не показывается', () => {
    const state = run(
      setCurrentCompany('A'),
      getCompanyProfile.pending('r1', 'A'),
      setCurrentCompany('B'),
      getCompanyProfile.rejected(null, 'r1', 'A', 'Сервер недоступен')
    )

    expect(state.error).toBeUndefined()
  })

  it('ответ по компании, которую уже сменили, не попадает в профиль', () => {
    const state = run(
      ...switchBackAndForth(),
      getCompanyProfile.fulfilled(profile('B', 'Компания B'), 'r2', 'B')
    )

    expect(state.profile).toBeNull()
    expect(state.loading).toBe(true)
  })
})
