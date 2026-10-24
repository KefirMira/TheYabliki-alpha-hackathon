import { useLayoutEffect, useRef, useState } from 'react'
import type { LucideIcon } from 'lucide-react'

import { cn } from '@/lib/utils'

export interface SegmentedOption<T extends string> {
  value: T
  label: string
  /** Счётчик справа от подписи («Риски 4»). */
  count?: number
  icon?: LucideIcon
}

interface SegmentedProps<T extends string> {
  options: SegmentedOption<NoInfer<T>>[]
  value: T
  // Тип значения выводится из value, а не из подписей опций.
  onChange: (value: NoInfer<T>) => void
  /** md — вкладки ленты и истории, sm — горизонт и мелкие переключатели. */
  size?: 'md' | 'sm'
  /** Во всю ширину, сегменты поровну — вкладки боковой панели. */
  fill?: boolean
  className?: string
  label?: string
}

interface IndicatorBox {
  left: number
  width: number
}

/**
 * Сегментный переключатель макета: серая подложка, активный сегмент белый
 * с лёгкой тенью. Белая плашка — отдельный слой под кнопками: при смене
 * значения она плавно переезжает к новому сегменту. Неактивные сегменты на
 * наведение не реагируют — только клик.
 */
const Segmented = <T extends string>({
  options,
  value,
  onChange,
  size = 'md',
  fill = false,
  className,
  label,
}: SegmentedProps<T>) => {
  const listRef = useRef<HTMLDivElement>(null)
  // Плашка появляется сразу на месте: новый элемент не анимируется, плавно
  // едет только смена положения.
  const [box, setBox] = useState<IndicatorBox | null>(null)
  const keys = options.map((option) => option.value).join('|')

  useLayoutEffect(() => {
    const list = listRef.current
    if (!list) return
    const measure = () => {
      const active = list.querySelector<HTMLElement>('[aria-selected="true"]')
      setBox(
        active ? { left: active.offsetLeft, width: active.offsetWidth } : null
      )
    }
    measure()
    // Ширина сегментов меняется: счётчики, подгрузка шрифта, жирность
    // активной подписи. jsdom в тестах ResizeObserver не знает.
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(measure)
    observer.observe(list)
    list
      .querySelectorAll('button')
      .forEach((button) => observer.observe(button))
    return () => observer.disconnect()
  }, [value, keys])

  return (
    <div
      ref={listRef}
      role="tablist"
      aria-label={label}
      className={cn(
        'relative max-w-full gap-0.5 rounded-xl bg-surface-chip p-[3px]',
        fill ? 'flex w-full' : 'inline-flex',
        className
      )}
    >
      {box && (
        <span
          aria-hidden="true"
          className="absolute bottom-[3px] left-0 top-[3px] rounded-[9px] bg-white shadow-[0_1px_2px_rgba(18,19,22,0.1)] transition-[transform,width] duration-300 ease-out motion-reduce:transition-none"
          style={{ width: box.width, transform: `translateX(${box.left}px)` }}
        />
      )}
      {options.map((option) => {
        const active = option.value === value
        const Icon = option.icon
        return (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(option.value)}
            className={cn(
              'relative inline-flex items-center justify-center whitespace-nowrap rounded-[9px]',
              size === 'md'
                ? 'gap-2 px-3.5 py-2 text-[15px]'
                : 'gap-1.5 px-2.5 py-[5px] text-[13px]',
              fill && 'flex-1 gap-1.5 px-2.5',
              active ? 'font-semibold' : 'font-medium'
            )}
          >
            {Icon && <Icon className="h-4 w-4" />}
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
}

export default Segmented
