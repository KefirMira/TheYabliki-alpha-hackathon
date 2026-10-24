import { type PayloadAction, createSlice } from '@reduxjs/toolkit'

import {
  storageDelete,
  storageGet,
  storageSave,
} from '@/shared/storage/storage'

/**
 * Вход — заглушка до подключения авторизации (JWT в бэкенде пока нет):
 * «Войти» сразу открывает интернет-банк. Сессия и логин живут в
 * sessionStorage, чтобы перезагрузка не выкидывала на экран входа.
 */
const SESSION_KEY = 'demo_session'
const USERNAME_KEY = 'demo_username'

/** Логин сохранённой сессии — по нему восстанавливаются компании. */
export const storedUsername = () => storageGet(USERNAME_KEY)

export interface AuthState {
  isAuthenticated: boolean
  /** Логин, под которым вошли, — пока единственные данные о пользователе. */
  username: string | null
}

const initialState: AuthState = {
  isAuthenticated: storageGet(SESSION_KEY) === '1',
  username: storageGet(USERNAME_KEY),
}

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    login: (state, action: PayloadAction<string>) => {
      state.isAuthenticated = true
      state.username = action.payload
      storageSave(SESSION_KEY, '1', false)
      storageSave(USERNAME_KEY, action.payload, false)
    },
    logout: (state) => {
      state.isAuthenticated = false
      state.username = null
      storageDelete(SESSION_KEY)
      storageDelete(USERNAME_KEY)
    },
  },
})

export const { login, logout } = authSlice.actions
export default authSlice.reducer
