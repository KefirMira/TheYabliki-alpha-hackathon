import { describe, expect, it } from 'vitest'

import { setCurrentCompany } from './CompanySlice'
import reducer, { hideInsight, toggleFavorite } from './PulseSlice'

const initial = () => reducer(undefined, { type: '@@init' })

describe('PulseSlice', () => {
  it('избранное по умолчанию пустое', () => {
    expect(initial().favorites).toEqual([])
  })

  it('переключение избранного добавляет и убирает', () => {
    const added = reducer(initial(), toggleFavorite('2'))
    expect(added.favorites).toEqual(['2'])
    expect(reducer(added, toggleFavorite('2')).favorites).toEqual([])
  })

  it('«Не относится к нам» скрывает инсайт и убирает из избранного', () => {
    const state = reducer(
      reducer(initial(), toggleFavorite('1')),
      hideInsight('1')
    )
    expect(state.hidden).toEqual(['1'])
    expect(state.favorites).toEqual([])
  })

  it('повторное скрытие не дублирует', () => {
    const state = reducer(
      reducer(initial(), hideInsight('1')),
      hideInsight('1')
    )
    expect(state.hidden).toEqual(['1'])
  })

  it('смена компании сбрасывает отметки', () => {
    const state = reducer(
      reducer(initial(), toggleFavorite('1')),
      setCurrentCompany('DEMO-002')
    )
    expect(state).toEqual(initial())
  })
})
