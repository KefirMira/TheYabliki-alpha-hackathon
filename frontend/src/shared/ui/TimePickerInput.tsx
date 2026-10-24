import { fieldClass } from '@/shared/ui/fieldStyles'
import {
  formatTimeInputValue,
  isDateTimeInputNavigationKey,
  isDigitKey,
} from '@/shared/utils/dateTimeInput'

interface TimePickerInputProps {
  /** «ЧЧ:ММ» или неполная строка, пока пользователь печатает. */
  value: string
  onChange: (value: string) => void
  id?: string
  invalid?: boolean
  placeholder?: string
}

/** Время по маске «ЧЧ:ММ»: двоеточие само, часы до 23, минуты до 59. */
const TimePickerInput = ({
  value,
  onChange,
  id,
  invalid = false,
  placeholder = 'ЧЧ:ММ',
}: TimePickerInputProps) => (
  <input
    id={id}
    value={value}
    inputMode="numeric"
    placeholder={placeholder}
    maxLength={5}
    className={fieldClass(invalid, 'tabular-nums')}
    onChange={(event) =>
      onChange(formatTimeInputValue(event.target.value, value))
    }
    onKeyDown={(event) => {
      if (event.ctrlKey || event.metaKey) return
      if (isDateTimeInputNavigationKey(event.key)) return
      if (!isDigitKey(event.key)) event.preventDefault()
    }}
  />
)

export default TimePickerInput
