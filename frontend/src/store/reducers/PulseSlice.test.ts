import { beforeEach, describe, expect, it } from 'vitest'

import { logout } from './AuthSlice'
import { setCurrentCompany } from './CompanySlice'
import reducer, {
  favoritesOwner,
  hideInsight,
  restoreHidden,
  toggleFavorite,
} from './PulseSlice'

const initial = () => reducer(undefined, { type: '@@init' })
const expert = favoritesOwner('Expert', 'DEMO-001')
const stored = (key = 'pulse_favorites') =>
  JSON.parse(localStorage.getItem(key) ?? '{}')

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})

describe('PulseSlice', () => {
  it('избранное по умолчанию пустое', () => {
    expect(initial().favoritesByOwner).toEqual({})
  })

  it('переключение избранного добавляет и убирает', () => {
    const added = reducer(initial(), toggleFavorite({ owner: expert, id: '2' }))
    expect(added.favoritesByOwner[expert]).toEqual(['2'])
    const removed = reducer(added, toggleFavorite({ owner: expert, id: '2' }))
    expect(removed.favoritesByOwner[expert]).toBeUndefined()
  })

  it('избранное сохраняется в браузере и читается после перезагрузки', () => {
    reducer(initial(), toggleFavorite({ owner: expert, id: '2' }))

    expect(stored()).toEqual({ 'expert|DEMO-001': ['2'] })
    // «Перезагрузка» — новое начальное состояние читает localStorage.
    expect(initial().favoritesByOwner[expert]).toEqual(['2'])
  })

  it('выход и смена компании избранное не трогают', () => {
    const state = [
      toggleFavorite({ owner: expert, id: '1' }),
      logout(),
      setCurrentCompany('DEMO-002'),
    ].reduce(reducer, initial())

    expect(state.favoritesByOwner[expert]).toEqual(['1'])
  })

  it('у разных логинов и компаний избранное своё', () => {
    const other = favoritesOwner('bakery', 'DEMO-001')
    const state = reducer(initial(), toggleFavorite({ owner: expert, id: '1' }))

    expect(state.favoritesByOwner[other]).toBeUndefined()
    expect(favoritesOwner(' EXPERT ', 'DEMO-001')).toBe(expert)
  })

  it('«Не относится к нам» скрывает инсайт и убирает из избранного', () => {
    const state = [
      toggleFavorite({ owner: expert, id: '1' }),
      hideInsight({ owner: expert, id: '1' }),
    ].reduce(reducer, initial())

    expect(state.hiddenByOwner[expert]).toEqual(['1'])
    expect(state.favoritesByOwner[expert]).toBeUndefined()
    expect(stored()).toEqual({})
  })

  it('скрытые сохраняются в браузере, переживают выход и смену компании', () => {
    const state = [
      hideInsight({ owner: expert, id: '1' }),
      hideInsight({ owner: expert, id: '1' }),
      logout(),
      setCurrentCompany('DEMO-002'),
    ].reduce(reducer, initial())

    expect(state.hiddenByOwner[expert]).toEqual(['1'])
    expect(stored('pulse_hidden')).toEqual({ 'expert|DEMO-001': ['1'] })
    // «Перезагрузка» читает скрытые из localStorage.
    expect(initial().hiddenByOwner[expert]).toEqual(['1'])
  })

  it('«Вернуть» возвращает в ленту все скрытые владельца', () => {
    const other = favoritesOwner('bakery', 'DEMO-001')
    const state = [
      hideInsight({ owner: expert, id: '1' }),
      hideInsight({ owner: other, id: '2' }),
      restoreHidden(expert),
    ].reduce(reducer, initial())

    expect(state.hiddenByOwner[expert]).toBeUndefined()
    expect(state.hiddenByOwner[other]).toEqual(['2'])
    expect(stored('pulse_hidden')).toEqual({ 'bakery|DEMO-001': ['2'] })
  })

  it('испорченный JSON в браузере не роняет ленту', () => {
    localStorage.setItem('pulse_favorites', '{"x": [1, 2], "y": ["3"]')
    expect(initial().favoritesByOwner).toEqual({})

    localStorage.setItem('pulse_favorites', '{"x": [1, 2], "y": ["3"]}')
    expect(initial().favoritesByOwner).toEqual({ y: ['3'] })
  })
})
