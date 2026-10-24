import { describe, expect, it } from 'vitest'

import { companiesForLogin, parseDemoAccounts, pickCompany } from './accounts'

const accounts = parseDemoAccounts(
  ' Expert = U_1, U_2 ;fuel=U_3;broken;empty=;'
)

describe('parseDemoAccounts', () => {
  it('разбирает логины без учёта регистра и пробелов, пропускает пустые', () => {
    expect(accounts).toEqual([
      { login: 'expert', companyIds: ['U_1', 'U_2'] },
      { login: 'fuel', companyIds: ['U_3'] },
    ])
  })
})

describe('companiesForLogin', () => {
  it('отдаёт компании логина независимо от регистра', () => {
    expect(companiesForLogin('EXPERT', accounts)).toEqual(['U_1', 'U_2'])
  })

  it('неизвестный логин — null', () => {
    expect(companiesForLogin('guest', accounts)).toBeNull()
  })

  it('без учёток любой логин видит все демо-компании', () => {
    expect(companiesForLogin('anyone', [], ['DEMO-001'])).toEqual(['DEMO-001'])
  })
})

describe('pickCompany', () => {
  it('сохраняет выбранную раньше компанию, если она доступна', () => {
    expect(pickCompany(['U_1', 'U_2'], 'U_2')).toBe('U_2')
  })

  it('чужую сохранённую компанию заменяет первой', () => {
    expect(pickCompany(['U_1', 'U_2'], 'U_9')).toBe('U_1')
  })

  it('без компаний — null', () => {
    expect(pickCompany([], null)).toBeNull()
  })
})
