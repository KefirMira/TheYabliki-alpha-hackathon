import { combineReducers } from '@reduxjs/toolkit'

// Слайсы доменов (auth, company, insights…) регистрируются здесь.
// Пока стор пустой: служебный срез нужен, чтобы combineReducers не ругался.
export const reducer = combineReducers({
  app: (state: Record<string, never> = {}) => state,
})
