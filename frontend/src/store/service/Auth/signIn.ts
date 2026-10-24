import {
  companiesForLogin,
  type IDemoAccount,
  pickCompany,
} from '@/shared/constants/accounts'
import { login } from '@/store/reducers/AuthSlice'
import { setCurrentCompany } from '@/store/reducers/CompanySlice'
import type { AppDispatch, RootState } from '@/store/types'

/**
 * Вход по тестовому логину: сессия и компания из компаний этого логина.
 * Возвращает false для неизвестного логина — тогда входа нет.
 *
 * Компанию переключаем, только если она меняется: setCurrentCompany
 * сбрасывает профиль, а повторная загрузка идёт по смене компании.
 */
export const signIn =
  (username: string, accounts?: IDemoAccount[]) =>
  (dispatch: AppDispatch, getState: () => RootState): boolean => {
    const companyIds = companiesForLogin(username, accounts)
    if (!companyIds) return false

    dispatch(login(username))
    const current = getState().company.currentCompanyId
    const next = pickCompany(companyIds, current)
    if (next && next !== current) dispatch(setCurrentCompany(next))
    return true
  }
