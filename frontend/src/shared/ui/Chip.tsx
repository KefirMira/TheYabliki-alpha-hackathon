import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

/** Серый чип признака («Кредит в Альфа-Банке», «ВЭД: Латвия, Польша»). */
const Chip = ({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) => (
  <span
    className={cn(
      'min-w-0 max-w-full truncate whitespace-nowrap rounded-md bg-surface-page px-2 py-1 text-xs leading-4 text-ink-2',
      className
    )}
  >
    {children}
  </span>
)

export default Chip
