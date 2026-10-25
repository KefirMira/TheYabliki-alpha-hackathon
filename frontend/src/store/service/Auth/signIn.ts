import {
  fetchMe,
  loginRequest,
  logoutRequest,
  type CurrentUser,
} from '@/shared/api/auth.api'
import { ApiError } from '@/shared/api/request'
import { accessToken, setAccessToken } from '@/shared/auth/session'
import { pickCompany } from '@/shared/constants/accounts'
import { storageGet } from '@/shared/storage/storage'
import { login, logout } from '@/store/reducers/AuthSlice'
import { setCurrentCompany } from '@/store/reducers/CompanySlice'
import type { AppDispatch } from '@/store/types'
const accept = (user: CurrentUser, dispatch: AppDispatch) => {
  dispatch(login(user))
  const selected = pickCompany(
    user.companies.map((c) => c.source_id),
    storageGet('current_company_id')
  )
  if (selected) dispatch(setCurrentCompany(selected))
}
export const signIn =
  (username: string, password: string) => async (dispatch: AppDispatch) => {
    try {
      const session = await loginRequest(username, password)
      setAccessToken(session.access_token)
      accept(await fetchMe(), dispatch)
    } catch (error) {
      dispatch(logout())
      throw error
    }
  }
export const restoreSession = () => async (dispatch: AppDispatch) => {
  if (!accessToken()) {
    dispatch(logout())
    return
  }
  try {
    accept(await fetchMe(), dispatch)
  } catch {
    dispatch(logout())
  }
}
export const signOut = () => async (dispatch: AppDispatch) => {
  try {
    if (accessToken()) await logoutRequest()
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 401)) throw error
  }
  dispatch(logout())
}
