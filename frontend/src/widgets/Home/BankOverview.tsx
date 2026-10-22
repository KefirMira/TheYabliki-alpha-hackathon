import {
  ArrowLeftRight,
  FilePlus,
  FileText,
  ScrollText,
  Upload,
} from 'lucide-react'

import { cn } from '@/lib/utils'
import {
  BANK_IN_WORK,
  HOME_ACCOUNTS,
  OPERATIONS,
  PAYMENT_STATUSES,
} from '@/shared/mocks/pulse'
import Card from '@/shared/ui/Card'

const QUICK_ACTIONS = [
  { label: 'Создать платёж', icon: FileText },
  { label: 'Между счетами', icon: ArrowLeftRight },
  { label: 'Выставить счёт', icon: FilePlus },
  { label: 'Импорт из 1С', icon: Upload },
  { label: 'Выписка', icon: ScrollText },
]

/** Быстрые действия банка — в прототипе только витрина. */
export const QuickActions = () => (
  <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
    {QUICK_ACTIONS.map(({ label, icon: Icon }) => (
      <span
        key={label}
        className="flex cursor-default items-center gap-3 rounded-2xl bg-white px-4 py-3.5 text-ink-2"
      >
        <Icon className="h-5 w-5 shrink-0" strokeWidth={1.8} />
        <span className="truncate text-[15px] font-medium text-ink">
          {label}
        </span>
      </span>
    ))}
  </div>
)

const Counter = ({ count, accent }: { count: number; accent?: boolean }) => (
  <span
    className={cn(
      'flex h-[22px] min-w-[22px] items-center justify-center rounded-full px-1.5 text-xs font-bold',
      accent ? 'bg-brand text-white' : 'bg-surface-chip'
    )}
  >
    {count}
  </span>
)

/** Статусы платежей: Подписать · Доработать · Черновики… */
export const PaymentStatuses = () => (
  <div className="flex flex-wrap items-center gap-x-7 gap-y-2 rounded-2xl bg-white px-5 py-3.5 text-[15px]">
    {PAYMENT_STATUSES.map((status) => (
      <span
        key={status.label}
        className={cn(
          'flex items-center gap-2',
          status.muted ? 'text-ink-3' : 'font-medium'
        )}
      >
        {status.label}
        <Counter count={status.count} accent={status.accent} />
      </span>
    ))}
    <span className="flex-1" />
    <span className="flex items-center gap-2 font-medium">
      В работе у банка
      <Counter count={BANK_IN_WORK} />
    </span>
  </div>
)

/** Расчётный счёт и кредитная линия. */
export const AccountCards = () => (
  <div className="grid gap-4 md:grid-cols-2">
    {HOME_ACCOUNTS.map((account) => (
      <Card key={account.title}>
        <div className="flex flex-col gap-1.5">
          <span className="text-[15px] text-ink-2">{account.title}</span>
          <span className="whitespace-nowrap text-[32px] font-bold tracking-[-0.01em]">
            {account.amount}
            <span className="text-ink-4">{account.cents}</span>
          </span>
          <span className="text-sm text-ink-3">{account.note}</span>
        </div>
      </Card>
    ))}
  </div>
)

/** История операций за день. */
export const OperationsHistory = () => (
  <Card>
    <div className="flex items-center justify-between">
      <span className="text-xl font-semibold">История операций</span>
      <span className="text-sm text-ink-3">15.09.2026</span>
    </div>
    <div className="flex flex-col">
      {OPERATIONS.map((operation) => (
        <div
          key={operation.counterparty}
          className="grid grid-cols-[80px_minmax(0,1fr)_200px] gap-4 border-t border-line py-3 text-[15px]"
        >
          <span className="text-ink-3">{operation.date}</span>
          <span className="truncate font-medium">{operation.counterparty}</span>
          <span
            className={cn(
              'text-right font-semibold',
              operation.income && 'text-tone-opp-fg'
            )}
          >
            {operation.amount}
          </span>
        </div>
      ))}
    </div>
  </Card>
)
