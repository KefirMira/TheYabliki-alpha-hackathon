import { cn } from '@/lib/utils'

export interface SegmentedOption<T extends string> {
  value: T
  label: string
  /** Счётчик справа от подписи («Риски 4»). */
  count?: number
}

interface SegmentedProps<T extends string> {
  options: SegmentedOption<NoInfer<T>>[]
  value: T
  // Тип значения выводится из value, а не из подписей опций.
  onChange: (value: NoInfer<T>) => void
  /** md — вкладки ленты и истории, sm — горизонт и мелкие переключатели. */
  size?: 'md' | 'sm'
  className?: string
  label?: string
}

/**
 * Сегментный переключатель макета: серая подложка, активный сегмент белый
 * с лёгкой тенью.
 */
const Segmented = <T extends string>({
  options,
  value,
  onChange,
  size = 'md',
  className,
  label,
}: SegmentedProps<T>) => (
  <div
    role="tablist"
    aria-label={label}
    className={cn(
      'inline-flex gap-0.5 rounded-xl bg-surface-chip p-[3px]',
      className
    )}
  >
    {options.map((option) => {
      const active = option.value === value
      return (
        <button
          key={option.value}
          type="button"
          role="tab"
          aria-selected={active}
          onClick={() => onChange(option.value)}
          className={cn(
            'inline-flex items-center justify-center whitespace-nowrap rounded-[9px] transition-colors',
            size === 'md'
              ? 'gap-2 px-3.5 py-2 text-[15px]'
              : 'gap-1.5 px-2.5 py-[5px] text-[13px]',
            active
              ? 'bg-white font-semibold shadow-[0_1px_2px_rgba(18,19,22,0.1)]'
              : 'font-medium hover:bg-white/50'
          )}
        >
          {option.label}
          {option.count !== undefined && (
            <span
              className={cn(
                'font-semibold tabular-nums text-ink-3',
                size === 'md' ? 'text-[13px]' : 'text-xs'
              )}
            >
              {option.count}
            </span>
          )}
        </button>
      )
    })}
  </div>
)

export default Segmented
