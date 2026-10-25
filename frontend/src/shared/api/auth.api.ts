import { apiRequest } from './request'
export interface Membership {
  source_id: string
  name: string | null
  can_analyze: boolean
}
export interface CurrentUser {
  user_id: string
  login: string
  companies: Membership[]
}
export const loginRequest = (login: string, password: string) =>
  apiRequest<{
    access_token: string
    token_type: 'bearer'
    expires_in: number
  }>(
    '/api/auth/login',
    { method: 'POST', body: JSON.stringify({ login, password }) },
    'Не удалось войти'
  )
export const fetchMe = () =>
  apiRequest<CurrentUser>(
    '/api/me',
    { method: 'GET' },
    'Не удалось проверить сессию'
  )
export const logoutRequest = () =>
  apiRequest<void>(
    '/api/auth/logout',
    { method: 'POST' },
    'Не удалось подтвердить выход. Попробуйте снова'
  )
