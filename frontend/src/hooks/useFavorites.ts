import { useCallback } from 'react'

import { useAppDispatch, useAppSelector } from '@/store/hooks/redux'
import {
  favoritesOwner,
  hideInsight,
  restoreHidden,
  toggleFavorite,
} from '@/store/reducers/PulseSlice'

const NO_FAVORITES: string[] = []

/**
 * Избранное и скрытые инсайты текущего логина и компании, действия с ними.
 * Владелец определяется здесь, чтобы страницы не собирали ключ сами.
 */
export const useFavorites = () => {
  const dispatch = useAppDispatch()
  const owner = useAppSelector((state) =>
    favoritesOwner(state.auth.username, state.company.currentCompanyId)
  )
  const favorites = useAppSelector(
    (state) => state.pulse.favoritesByOwner[owner] ?? NO_FAVORITES
  )

  const toggle = useCallback(
    (id: string) => dispatch(toggleFavorite({ owner, id })),
    [dispatch, owner]
  )
  const hide = useCallback(
    (id: string) => dispatch(hideInsight({ owner, id })),
    [dispatch, owner]
  )
  const restoreAllHidden = useCallback(
    () => dispatch(restoreHidden(owner)),
    [dispatch, owner]
  )

  return { favorites, toggle, hide, restoreAllHidden }
}
