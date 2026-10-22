import { cn } from '@/lib/utils'

/** Поле ввода макета: серая подложка, без рамки, обводка при фокусе. */
export const fieldClass = (invalid = false, className?: string) =>
  cn(
    'h-12 w-full rounded-xl border-none bg-surface-page px-3.5 text-[15px] text-ink outline-none transition-shadow placeholder:text-ink-4',
    'focus:shadow-[inset_0_0_0_1.5px_#121316]',
    invalid && 'shadow-[inset_0_0_0_1.5px_#B42318]',
    className
  )

/** Подпись поля над ним. */
export const fieldLabelClass = 'text-[13px] text-ink-3'
