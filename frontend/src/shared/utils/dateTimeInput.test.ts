import { describe, expect, it } from 'vitest'

import {
  composeDateTime,
  formatDateInput,
  formatTimeInputValue,
  parseDateFromUiString,
} from './dateTimeInput'

describe('formatDateInput', () => {
  it('подставляет точки по мере ввода цифр', () => {
    expect(formatDateInput('24', 2).value).toBe('24')
    expect(formatDateInput('2410', 4).value).toBe('24.10')
    expect(formatDateInput('24102026', 8)).toEqual({
      value: '24.10.2026',
      newCursorPosition: 10,
    })
  })

  it('отбрасывает буквы и лишние цифры', () => {
    expect(formatDateInput('2a4.10.20261', 12).value).toBe('24.10.2026')
  })
})

describe('formatTimeInputValue', () => {
  it('подставляет двоеточие и ограничивает часы и минуты', () => {
    expect(formatTimeInputValue('0930')).toBe('09:30')
    expect(formatTimeInputValue('2975')).toBe('23:59')
  })

  it('стирание не переформатирует', () => {
    expect(formatTimeInputValue('09:', '09:3')).toBe('09:')
  })
})

describe('parseDateFromUiString', () => {
  it('несуществующая или неполная дата — undefined', () => {
    expect(parseDateFromUiString('31.02.2026')).toBeUndefined()
    expect(parseDateFromUiString('24.10.20')).toBeUndefined()
    expect(parseDateFromUiString('24.10.2026')).toEqual(new Date(2026, 9, 24))
  })
})

describe('composeDateTime', () => {
  it('дата и время → формат формы, без времени — полночь', () => {
    expect(composeDateTime('24.10.2026', '15:30')).toBe('2026-10-24T15:30')
    expect(composeDateTime('24.10.2026', '')).toBe('2026-10-24T00:00')
  })

  it('пустые поля — пустая строка, неполные — ошибка', () => {
    expect(composeDateTime('', '')).toBe('')
    expect(composeDateTime('', '15:30')).toBeNull()
    expect(composeDateTime('24.10', '')).toBeNull()
    expect(composeDateTime('24.10.2026', '15:3')).toBeNull()
  })
})
