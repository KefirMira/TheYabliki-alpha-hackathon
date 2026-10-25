import { createSelector } from '@reduxjs/toolkit'

import { companyNameOf } from '@/shared/api/mappers/companyMappers'
import { mapFeedItem } from '@/shared/api/mappers/pulseMappers'

import { favoritesOwner } from '../reducers/PulseSlice'
import type { RootState } from '../types'

const NO_IDS: string[] = []

/** Скрытые «Не относится к нам» текущего логина и компании. */
export const selectHiddenIds = (state: RootState) =>
  state.pulse.hiddenByOwner[
    favoritesOwner(state.auth.username, state.company.currentCompanyId)
  ] ?? NO_IDS

/**
 * Лента из API в моделях экрана, без скрытых «Не относится к нам».
 * Пришедшие при фоновом обновлении и ещё не открытые помечены «Новое».
 */
export const selectPulseInsights = createSelector(
  [
    (state: RootState) => state.insights.items,
    selectHiddenIds,
    (state: RootState) => state.insights.newIds,
  ],
  (items, hidden, newIds) =>
    items
      .map((item) => {
        const insight = mapFeedItem(item)
        return newIds.includes(item.insight_id)
          ? { ...insight, isNew: true, updated: `Новое · ${insight.updated}` }
          : insight
      })
      .filter((insight) => !hidden.includes(insight.id))
)

/** Название компании для шапки: name, а без него — идентификатор. */
export const selectCompanyTitle = (state: RootState) => {
  const { profile, currentCompanyId } = state.company
  if (profile) return companyNameOf(profile)
  return currentCompanyId ?? 'Компания не выбрана'
}

const companyIds = createSelector(
  [(state: RootState) => state.auth.companies],
  (companies) => companies.map((c) => c.source_id)
)

/** Компании, доступные логину сессии, — для переключателя в шапке. */
export const selectUserCompanyIds = (state: RootState) => companyIds(state)
