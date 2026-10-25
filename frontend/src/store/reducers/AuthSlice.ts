import { type PayloadAction, createSlice } from '@reduxjs/toolkit'
import type { CurrentUser, Membership } from '@/shared/api/auth.api'
import { accessToken, clearSession } from '@/shared/auth/session'
export interface AuthState {
  isAuthenticated: boolean
  checking: boolean
  username: string | null
  userId: string | null
  companies: Membership[]
}
const initialState: AuthState = {
  isAuthenticated: false,
  checking: Boolean(accessToken()),
  username: null,
  userId: null,
  companies: [],
}
const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    login: (state, action: PayloadAction<CurrentUser>) => {
      state.isAuthenticated = true
      state.checking = false
      state.username = action.payload.login
      state.userId = action.payload.user_id
      state.companies = action.payload.companies
    },
    logout: (state) => {
      clearSession()
      state.isAuthenticated = false
      state.checking = false
      state.username = null
      state.userId = null
      state.companies = []
    },
  },
})
export const { login, logout } = authSlice.actions
export default authSlice.reducer
