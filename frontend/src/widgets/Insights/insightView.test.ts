import { describe, expect, it } from 'vitest'

import { PULSE_INSIGHTS } from '@/shared/mocks/pulse'

import { fitChips, kindTagText, relevanceText } from './insightView'

describe('insightView', () => {
  it('тег — тип и уровень влияния', () => {
    expect(kindTagText(PULSE_INSIGHTS.rate)).toBe('Риск · Высокое')
    expect(kindTagText(PULSE_INSIGHTS.ofz)).toBe('Возможность · Низкое')
  })

  it('у гипотезы вместо релевантности — сила данных', () => {
    expect(relevanceText(PULSE_INSIGHTS.rate)).toBe('94%')
    expect(relevanceText(PULSE_INSIGHTS.rate, true)).toBe(
      'Релевантность для вас: 94%'
    )
    expect(relevanceText(PULSE_INSIGHTS.eu)).toBe('Сила данных: средняя')
  })

  it('чипы: первый всегда виден, длинный второй уходит в «+1»', () => {
    expect(fitChips(['Кредит в Альфа-Банке', 'Лизинг'])).toEqual({
      visible: ['Кредит в Альфа-Банке'],
      more: 1,
    })
  })

  it('чипы: не больше двух даже если коротких больше', () => {
    expect(fitChips(['А', 'Б', 'В'])).toEqual({ visible: ['А', 'Б'], more: 1 })
  })
})
