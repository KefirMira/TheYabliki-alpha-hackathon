/**
 * Ввод даты и времени с клавиатуры по маске: «ДД.ММ.ГГГГ» и «ЧЧ:ММ».
 * Точки и двоеточие подставляются сами, лишние символы не вводятся.
 */

const UI_DATE_PATTERN = /^\d{2}\.\d{2}\.\d{4}$/
const UI_TIME_PATTERN = /^\d{2}:\d{2}$/

const isValidDate = (day: number, month: number, year: number) => {
  if (year < 1900 || year > 2100) return false
  if (month < 1 || month > 12) return false
  return day >= 1 && day <= new Date(year, month, 0).getDate()
}

/** «24.10.2026» → Date; неполная или несуществующая дата — undefined. */
export const parseDateFromUiString = (value: string): Date | undefined => {
  if (!UI_DATE_PATTERN.test(value)) return undefined
  const [day, month, year] = value.split('.').map(Number)
  if (!isValidDate(day, month, year)) return undefined
  return new Date(year, month - 1, day)
}

/** Маска даты: цифры → «ДД.ММ.ГГГГ», курсор остаётся после той же цифры. */
export const formatDateInput = (
  input: string,
  cursorPosition: number
): { value: string; newCursorPosition: number } => {
  const digits = input.replace(/\D/g, '').slice(0, 8)
  const digitsBeforeCursor = input
    .slice(0, cursorPosition)
    .replace(/\D/g, '').length

  let value = digits
  if (digits.length > 4) {
    value = `${digits.slice(0, 2)}.${digits.slice(2, 4)}.${digits.slice(4)}`
  } else if (digits.length > 2) {
    value = `${digits.slice(0, 2)}.${digits.slice(2)}`
  }

  let newCursorPosition = digitsBeforeCursor
  if (digitsBeforeCursor > 2) newCursorPosition += 1
  if (digitsBeforeCursor > 4) newCursorPosition += 1

  return { value, newCursorPosition: Math.min(newCursorPosition, value.length) }
}

/**
 * Маска времени: цифры → «ЧЧ:ММ», часы не больше 23, минуты — 59.
 * Стирание не переформатируется, чтобы Backspace работал как обычно.
 */
export const formatTimeInputValue = (input: string, previousValue = '') => {
  if (input.length < previousValue.length) return input

  let digits = input.replace(/\D/g, '').slice(0, 4)
  if (digits.length >= 2) {
    const hours = Math.min(23, Number(digits.slice(0, 2)))
    digits = `${String(hours).padStart(2, '0')}${digits.slice(2)}`
  }
  if (digits.length >= 4) {
    const minutes = Math.min(59, Number(digits.slice(2, 4)))
    digits = `${digits.slice(0, 2)}${String(minutes).padStart(2, '0')}`
  }

  return digits.length > 2 ? `${digits.slice(0, 2)}:${digits.slice(2)}` : digits
}

/** Клавиши, которые полям даты и времени нельзя запрещать. */
export const isDateTimeInputNavigationKey = (key: string) =>
  [
    'Backspace',
    'Delete',
    'ArrowLeft',
    'ArrowRight',
    'Tab',
    'Home',
    'End',
    'Enter',
  ].includes(key)

export const isDigitKey = (key: string) => /^\d$/.test(key)

/**
 * Дата и время из полей → «ГГГГ-ММ-ДДTЧЧ:ММ» (местное время, как у
 * datetime-local). Пустая дата — пустая строка; без времени — полночь.
 * Неполная дата или время — null: это ошибка формы.
 */
export const composeDateTime = (date: string, time: string): string | null => {
  if (!date.trim()) return time.trim() ? null : ''
  const parsed = parseDateFromUiString(date)
  if (!parsed) return null
  const clock = time.trim() || '00:00'
  if (!UI_TIME_PATTERN.test(clock)) return null
  const [year, month, day] = [
    parsed.getFullYear(),
    String(parsed.getMonth() + 1).padStart(2, '0'),
    String(parsed.getDate()).padStart(2, '0'),
  ]
  return `${year}-${month}-${day}T${clock}`
}
