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
import DemoStub from '@/shared/ui/DemoStub'

const QUICK_ACTIONS = [
  { label: 'Создать платёж', icon: FileText },
  { label: 'Между счетами', icon: ArrowLeftRight },
  { label: 'Выставить счёт', icon: FilePlus },
  { label: 'Импорт из 1С', icon: Upload },
  { label: 'Выписка', icon: ScrollText },
]

/**
 * Витрина интернет-банка вокруг Пульса. Действия и статусы — DemoStub
 * (приглушены, по клику подсказка). Счета и операции — данные для
 * контекста: приглушены слабее и на клик не реагируют.
 */
const INFO_DIM = 'opacity-75'

/**
 * Быстрые действия банка — в прототипе не работают. На узком экране —
 * плитки «значок над подписью», как в мобильном банке; с lg — строкой.
 */
export const QuickActions = () => (
  <div className="grid grid-cols-5 gap-2 md:gap-3">
    {QUICK_ACTIONS.map(({ label, icon: Icon }) => (
      <DemoStub
        key={label}
        label={label}
        className="flex min-w-0 flex-col items-center gap-1.5 rounded-2xl bg-white px-1 py-3 text-center text-ink-2 lg:flex-row lg:gap-3 lg:px-4 lg:py-3.5 lg:text-left"
      >
        <Icon className="h-5 w-5 shrink-0" strokeWidth={1.8} />
        <span className="line-clamp-2 text-xs font-medium leading-4 text-ink sm:text-[13px] lg:line-clamp-1 lg:text-[15px] lg:leading-normal">
          {label}
        </span>
      </DemoStub>
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
  <DemoStub
    label="Статусы платежей"
    className="flex flex-wrap items-center gap-x-7 gap-y-2 rounded-2xl bg-white px-5 py-3.5 text-[15px]"
  >
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
  </DemoStub>
)

/** Расчётный счёт и кредитная линия. */
export const AccountCards = () => (
  <div className={cn('grid gap-4 md:grid-cols-2', INFO_DIM)}>
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
  <Card className={INFO_DIM}>
    <div className="flex items-center justify-between">
      <span className="text-xl font-semibold">История операций</span>
      <span className="text-sm text-ink-3">15.09.2026</span>
    </div>
    <div className="flex flex-col">
      {OPERATIONS.map((operation) => (
        <div
          key={operation.counterparty}
          className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 border-t border-line py-3 text-[15px] md:grid-cols-[80px_minmax(0,1fr)_200px] md:gap-4"
        >
          <span className="hidden text-ink-3 md:block">{operation.date}</span>
          {/* На узком экране дата — под контрагентом, сумма справа. */}
          <span className="flex min-w-0 flex-col">
            <span className="truncate font-medium">
              {operation.counterparty}
            </span>
            <span className="text-[13px] text-ink-3 md:hidden">
              {operation.date}
            </span>
          </span>
          <span
            className={cn(
              'whitespace-nowrap text-right font-semibold',
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
