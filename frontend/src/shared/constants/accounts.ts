import { DEMO_COMPANY_IDS } from './companies'

/**
 * Тестовые учётки для экспертов: логин → компании. Авторизации в API пока
 * нет, поэтому список задаётся при сборке:
 * VITE_DEMO_ACCOUNTS="expert=U_1,U_2;fuel=U_3". Пароль не проверяется.
 */
export interface IDemoAccount {
  login: string
  companyIds: string[]
}

const normalize = (login: string) => login.trim().toLowerCase()

export const parseDemoAccounts = (raw: string): IDemoAccount[] =>
  raw
    .split(';')
    .map((entry) => {
      const [login = '', ids = ''] = entry.split('=')
      return {
        login: normalize(login),
        companyIds: ids
          .split(',')
          .map((id) => id.trim())
          .filter(Boolean),
      }
    })
    .filter((account) => account.login && account.companyIds.length > 0)

export const DEMO_ACCOUNTS = parseDemoAccounts(
  import.meta.env.VITE_DEMO_ACCOUNTS ?? ''
)

/**
 * Компании логина. Без настроенных учёток подходит любой логин и видит все
 * демо-компании — так удобно разработке. С учётками неизвестный логин даёт
 * null: войти под ним нельзя.
 */
export const companiesForLogin = (
  login: string | null,
  accounts: IDemoAccount[] = DEMO_ACCOUNTS,
  fallback: string[] = DEMO_COMPANY_IDS
): string[] | null => {
  if (accounts.length === 0) return fallback
  if (!login) return null
  return (
    accounts.find((account) => account.login === normalize(login))
      ?.companyIds ?? null
  )
}

/** Компания после входа: сохранённая, если она доступна логину, иначе первая. */
export const pickCompany = (
  companyIds: string[],
  saved: string | null
): string | null =>
  saved && companyIds.includes(saved) ? saved : (companyIds[0] ?? null)
