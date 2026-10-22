import { describe, expect, it } from 'vitest'

import { insightTypeMeta, relevanceLabel } from './insightPresentation'

describe('insightPresentation', () => {
  it('у каждого типа своя подпись', () => {
    expect(insightTypeMeta('risk').label).toBe('Риск')
    expect(insightTypeMeta('opportunity').label).toBe('Возможность')
    expect(insightTypeMeta('mixed').label).toBe('Риск и возможность')
    expect(insightTypeMeta('information').label).toBe('Информация')
  })

  it('неизвестный тип не угадывается', () => {
    expect(insightTypeMeta(null).label).toBe('Инсайт')
  })

  it('релевантность unknown и null не показывается', () => {
    expect(relevanceLabel('high')).toBe('Высокая релевантность')
    expect(relevanceLabel('unknown')).toBeNull()
    expect(relevanceLabel(null)).toBeNull()
  })
})
