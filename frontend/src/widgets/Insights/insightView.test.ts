import { describe, expect, it } from 'vitest'

import type { IPulseInsight } from '@/store/models/IPulse'

import { relevanceText } from './insightView'

const insight = (patch: Partial<IPulseInsight> = {}): IPulseInsight => ({
  id: '1',
  kind: 'risk',
  title: 'Инсайт',
  updated: 'Анализ от 2 января 2026',
  ageHours: 1,
  ...patch,
})

describe('relevanceText', () => {
  it('уровень из API — словами', () => {
    expect(relevanceText(insight({ relevanceLevel: 'high' }))).toBe(
      'Высокая релевантность'
    )
  })

  it('без уровня — пусто, ничего не рисуем', () => {
    expect(relevanceText(insight())).toBe('')
  })
})
