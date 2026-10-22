import { cn } from '@/lib/utils'

interface SwitchProps {
  checked: boolean
  onChange?: (checked: boolean) => void
  /** Всегда включено и не меняется (лента в интернет-банке). */
  locked?: boolean
  label: string
}

/** Переключатель 40×24: чёрный — включено, серый — выключено. */
const Switch = ({ checked, onChange, locked = false, label }: SwitchProps) => (
  <button
    type="button"
    role="switch"
    aria-checked={checked}
    aria-label={label}
    disabled={locked}
    onClick={() => onChange?.(!checked)}
    className={cn(
      'relative block h-6 w-10 shrink-0 rounded-full transition-colors',
      checked ? 'bg-ink' : 'bg-surface-off',
      locked ? 'cursor-not-allowed opacity-35' : 'cursor-pointer'
    )}
  >
    <span
      className={cn(
        'absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-[left]',
        checked ? 'left-[18px]' : 'left-0.5'
      )}
    />
  </button>
)

export default Switch
