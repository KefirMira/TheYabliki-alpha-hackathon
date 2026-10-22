import type { HTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

/** Белая карточка макета: радиус 20 (rounded-3xl), отступ 20, шаг 16. */
const Card = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
      'flex min-w-0 flex-col gap-4 rounded-3xl bg-white p-5',
      className
    )}
    {...props}
  />
)

export default Card
