import { useRef, useState } from 'react'
import { format } from 'date-fns'
import { CalendarDays } from 'lucide-react'
import type { Matcher } from 'react-day-picker'

import { Calendar } from '@/components/ui/calendar'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { fieldClass } from '@/shared/ui/fieldStyles'
import {
  formatDateInput,
  isDateTimeInputNavigationKey,
  isDigitKey,
  parseDateFromUiString,
} from '@/shared/utils/dateTimeInput'

interface DatePickerInputProps {
  /** «ДД.ММ.ГГГГ» или неполная строка, пока пользователь печатает. */
  value: string
  onChange: (value: string) => void
  id?: string
  invalid?: boolean
  disabledDates?: Matcher | Matcher[]
  placeholder?: string
}

/**
 * Дата: печатается с клавиатуры по маске «ДД.ММ.ГГГГ» или выбирается в
 * календаре по кнопке справа. Нативный datetime-local не используем — он
 * выглядит по-разному в каждом браузере и неудобен на телефоне.
 */
const DatePickerInput = ({
  value,
  onChange,
  id,
  invalid = false,
  disabledDates,
  placeholder = 'ДД.ММ.ГГГГ',
}: DatePickerInputProps) => {
  const [open, setOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <div className="relative">
      <input
        id={id}
        ref={inputRef}
        value={value}
        inputMode="numeric"
        placeholder={placeholder}
        maxLength={10}
        className={fieldClass(invalid, 'pr-12 tabular-nums')}
        onChange={(event) => {
          const { value: next, newCursorPosition } = formatDateInput(
            event.target.value,
            event.target.selectionStart ?? 0
          )
          onChange(next)
          // Точки подставились — курсор остаётся после той же цифры.
          setTimeout(() =>
            inputRef.current?.setSelectionRange(
              newCursorPosition,
              newCursorPosition
            )
          )
        }}
        onKeyDown={(event) => {
          if (event.ctrlKey || event.metaKey) return
          if (isDateTimeInputNavigationKey(event.key)) return
          if (!isDigitKey(event.key)) event.preventDefault()
        }}
      />
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger
          type="button"
          aria-label="Выбрать дату в календаре"
          className="absolute right-1.5 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-lg text-ink-3 transition-colors hover:bg-surface-chip hover:text-ink"
        >
          <CalendarDays className="h-[18px] w-[18px]" />
        </PopoverTrigger>
        <PopoverContent
          align="end"
          collisionPadding={12}
          className="w-auto max-w-[calc(100vw-24px)] p-0"
        >
          <Calendar
            selected={parseDateFromUiString(value)}
            disabled={disabledDates}
            onSelect={(date) => {
              if (!date) return
              onChange(format(date, 'dd.MM.yyyy'))
              setOpen(false)
            }}
            initialFocus
          />
        </PopoverContent>
      </Popover>
    </div>
  )
}

export default DatePickerInput
