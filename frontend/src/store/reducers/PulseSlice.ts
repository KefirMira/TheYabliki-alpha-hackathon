import { type PayloadAction, createSlice } from '@reduxjs/toolkit'

import { storageGet, storageSave } from '@/shared/storage/storage'

/** Ключи отметок в localStorage: все логины и компании одним JSON. */
const FAVORITES_KEY = 'pulse_favorites'
const HIDDEN_KEY = 'pulse_hidden'

/** Отметки по владельцу «логин|компания»: id инсайтов. */
type OwnerLists = Record<string, string[]>

/**
 * Пользовательские отметки инсайтов: избранное (лента и страница инсайта) и
 * скрытые «Не относится к нам». В БД для них есть company_insight_states, но
 * API пока нет.
 *
 * Отметки хранятся в браузере по владельцу «логин|компания» и переживают
 * перезагрузку, выход и повторный вход: у каждого логина и компании свои.
 */
export interface PulseState {
  favoritesByOwner: OwnerLists
  hiddenByOwner: OwnerLists
}

/** Владелец отметок: логин без учёта регистра и компания. */
export const favoritesOwner = (
  login: string | null,
  companyId: string | null
) => `${(login ?? '').trim().toLowerCase()}|${companyId ?? ''}`

interface MarkAction {
  owner: string
  id: string
}

const load = (key: string): OwnerLists => {
  try {
    const parsed: unknown = JSON.parse(storageGet(key) ?? '{}')
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return {}
    }
    // Чужой или испорченный JSON не должен уронить ленту.
    return Object.fromEntries(
      Object.entries(parsed).filter(
        (entry): entry is [string, string[]] =>
          Array.isArray(entry[1]) &&
          entry[1].every((id) => typeof id === 'string')
      )
    )
  } catch {
    return {}
  }
}

const save = (key: string, lists: OwnerLists) =>
  storageSave(key, JSON.stringify(lists))

const add = (lists: OwnerLists, { owner, id }: MarkAction) => {
  if (!lists[owner]?.includes(id)) lists[owner] = [...(lists[owner] ?? []), id]
}

const remove = (lists: OwnerLists, { owner, id }: MarkAction) => {
  const list = (lists[owner] ?? []).filter((item) => item !== id)
  if (list.length > 0) lists[owner] = list
  else delete lists[owner]
}

const initialState = (): PulseState => ({
  favoritesByOwner: load(FAVORITES_KEY),
  hiddenByOwner: load(HIDDEN_KEY),
})

const pulseSlice = createSlice({
  name: 'pulse',
  initialState,
  reducers: {
    toggleFavorite: (state, action: PayloadAction<MarkAction>) => {
      const { owner, id } = action.payload
      if (state.favoritesByOwner[owner]?.includes(id)) {
        remove(state.favoritesByOwner, action.payload)
      } else {
        add(state.favoritesByOwner, action.payload)
      }
      save(FAVORITES_KEY, state.favoritesByOwner)
    },
    /** «Не относится к нам»: скрыть из ленты и убрать из избранного. */
    hideInsight: (state, action: PayloadAction<MarkAction>) => {
      add(state.hiddenByOwner, action.payload)
      remove(state.favoritesByOwner, action.payload)
      save(HIDDEN_KEY, state.hiddenByOwner)
      save(FAVORITES_KEY, state.favoritesByOwner)
    },
    /** Вернуть в ленту все скрытые инсайты владельца. */
    restoreHidden: (state, action: PayloadAction<string>) => {
      delete state.hiddenByOwner[action.payload]
      save(HIDDEN_KEY, state.hiddenByOwner)
    },
  },
})

export const { toggleFavorite, hideInsight, restoreHidden } = pulseSlice.actions
export default pulseSlice.reducer
