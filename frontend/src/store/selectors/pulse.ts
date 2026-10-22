import { createSelector } from '@reduxjs/toolkit'

import { companyNameOf } from '@/shared/api/mappers/companyMappers'
import { mapFeedItem } from '@/shared/api/mappers/pulseMappers'

import type { RootState } from '../types'

/** Лента из API в моделях экрана, без скрытых «Не относится к нам». */
export const selectPulseInsights = createSelector(
  [
    (state: RootState) => state.insights.items,
    (state: RootState) => state.pulse.hidden,
  ],
  (items, hidden) =>
    items
      .map((item) => mapFeedItem(item))
      .filter((insight) => !hidden.includes(insight.id))
)

/** Название компании для шапки: name, а без него — идентификатор. */
export const selectCompanyTitle = (state: RootState) => {
  const { profile, currentCompanyId } = state.company
  if (profile) return companyNameOf(profile)
  return currentCompanyId ?? 'Компания не выбрана'
}
