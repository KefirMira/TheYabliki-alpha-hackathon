import { type PayloadAction, createSlice } from '@reduxjs/toolkit'

import { setCurrentCompany } from './CompanySlice'

/**
 * Пользовательские отметки инсайтов: избранное (лента и страница инсайта) и
 * скрытые «Не относится к нам». В БД для них есть company_insight_states, но
 * API пока нет — отметки живут в сторе до перезагрузки.
 */
export interface PulseState {
  favorites: string[]
  hidden: string[]
}

const initialState: PulseState = {
  favorites: [],
  hidden: [],
}

const pulseSlice = createSlice({
  name: 'pulse',
  initialState,
  reducers: {
    toggleFavorite: (state, action: PayloadAction<string>) => {
      const id = action.payload
      state.favorites = state.favorites.includes(id)
        ? state.favorites.filter((item) => item !== id)
        : [...state.favorites, id]
    },
    hideInsight: (state, action: PayloadAction<string>) => {
      if (!state.hidden.includes(action.payload)) {
        state.hidden.push(action.payload)
      }
      state.favorites = state.favorites.filter((id) => id !== action.payload)
    },
  },
  extraReducers: (builder) => {
    // Отметки относятся к инсайтам компании: при смене компании — заново.
    builder.addCase(setCurrentCompany, () => initialState)
  },
})

export const { toggleFavorite, hideInsight } = pulseSlice.actions
export default pulseSlice.reducer
