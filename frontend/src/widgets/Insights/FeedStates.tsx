import type { ReactNode } from 'react'
import { AlertCircle, Inbox, RotateCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import Card from '@/shared/ui/Card'
import { Skeleton } from '@/components/ui/skeleton'

/** Каркас карточек, пока лента грузится. */
export const FeedSkeleton = ({
  count = 4,
  className,
}: {
  count?: number
  className?: string
}) => (
  <div className={cn('grid gap-4 md:grid-cols-2', className)} aria-busy="true">
    {Array.from({ length: count }, (_, index) => (
      <div
        key={index}
        className="flex flex-col gap-4 rounded-[20px] bg-white p-5"
      >
        <Skeleton className="h-[22px] w-40 bg-surface-page" />
        <Skeleton className="h-5 w-full bg-surface-page" />
        <Skeleton className="h-5 w-2/3 bg-surface-page" />
        <Skeleton className="h-4 w-32 bg-surface-page" />
      </div>
    ))}
  </div>
)

/** Пустое состояние или ошибка: иконка, заголовок, пояснение, действие. */
export const FeedMessage = ({
  error = false,
  title,
  text,
  action,
}: {
  error?: boolean
  title: string
  text: string
  action?: ReactNode
}) => {
  const Icon = error ? AlertCircle : Inbox
  return (
    <Card className="items-center gap-2.5 py-12 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-surface-page text-ink-3">
        <Icon className="h-6 w-6" />
      </span>
      <span className="text-lg font-semibold">{title}</span>
      <span className="max-w-md text-[15px] text-ink-2">{text}</span>
      {action}
    </Card>
  )
}

/**
 * Компания не выбрана: без неё запрос ленты не уходит, и скелетон висел бы
 * бесконечно. Например, если сборку забыли собрать с VITE_DEMO_COMPANY_IDS.
 */
export const NoCompanyMessage = () => (
  <FeedMessage
    title="Компания не выбрана"
    text="Выберите компанию в шапке интернет-банка."
  />
)

export const RetryButton = ({ onClick }: { onClick: () => void }) => (
  <Button variant="secondary" onClick={onClick} className="mt-1">
    <RotateCw />
    Повторить
  </Button>
)
