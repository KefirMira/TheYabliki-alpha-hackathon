import { Bell, FileSignature } from 'lucide-react'
import { Link } from 'react-router-dom'

import {
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { cn } from '@/lib/utils'
import { BELL_PAYMENT } from '@/shared/mocks/pulse'
import DemoStub from '@/shared/ui/DemoStub'
import PulseLogo from '@/shared/ui/PulseLogo'
import { useAppSelector } from '@/store/hooks/redux'
import { selectPulseInsights } from '@/store/selectors/pulse'
import InsightKindTag from '@/widgets/Insights/InsightKindTag'
import { filterFeed, filtersFromParams } from '@/widgets/Insights/feedFilter'

const iconButton =
  'relative flex h-10 w-10 items-center justify-center rounded-xl text-ink-2 transition-colors hover:bg-surface-chip'

const PULSE_NOTIFICATIONS = 2

/**
 * Колокольчик: важные события Пульса приходят сюда пушем. Инсайты — из API,
 * платёж на подпись — часть оболочки интернет-банка.
 */
const NotificationsBell = () => {
  const all = useAppSelector(selectPulseInsights)
  const insights = filterFeed(
    all,
    filtersFromParams(new URLSearchParams()),
    []
  ).items.slice(0, PULSE_NOTIFICATIONS)
  const count = insights.length + 1

  return (
    <Popover>
      <PopoverTrigger
        className={cn(iconButton, 'data-[state=open]:bg-surface-chip')}
        aria-label={`Уведомления: ${count}`}
      >
        <Bell className="h-5 w-5" strokeWidth={1.8} />
        <span className="absolute right-0.5 top-[3px] flex h-[18px] min-w-[18px] items-center justify-center rounded-full border-2 border-surface-page bg-brand px-[5px] text-[11px] font-bold text-white">
          {count}
        </span>
      </PopoverTrigger>
      <PopoverContent
        collisionPadding={16}
        className="flex w-[min(400px,calc(100vw-32px))] flex-col"
      >
        <div className="flex items-center justify-between px-3 pb-2 pt-3">
          <span className="text-[17px] font-semibold">Уведомления</span>
          <DemoStub label="Прочитать все" className="text-[13px] text-ink-3">
            Прочитать все
          </DemoStub>
        </div>

        {insights.map((insight, index) => (
          <PopoverClose asChild key={insight.id}>
            <Link
              to={`/pulse/insights/${insight.id}`}
              className={cn(
                'flex gap-3 rounded-[14px] p-3',
                index === 0 ? 'bg-surface-page' : 'hover:bg-surface-page'
              )}
            >
              <PulseLogo className="h-7 w-7" />
              <span className="flex min-w-0 flex-col gap-1.5">
                <span className="flex flex-wrap items-center gap-2">
                  <InsightKindTag insight={insight} />
                  <span className="text-xs text-ink-3">Пульс бизнеса</span>
                </span>
                <span className="line-clamp-2 text-[15px] font-semibold leading-[1.35]">
                  {insight.title}
                </span>
                <span className="text-[13px] text-ink-3">
                  {insight.updated}
                </span>
              </span>
            </Link>
          </PopoverClose>
        ))}

        <DemoStub
          label="Платёж на подпись"
          className="flex gap-3 rounded-[14px] p-3"
        >
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-surface-page text-ink-2">
            <FileSignature className="h-4 w-4" />
          </span>
          <span className="flex flex-1 flex-col gap-1">
            <span className="flex justify-between gap-2">
              <span className="text-[15px] font-medium">
                {BELL_PAYMENT.title}
              </span>
              <span className="whitespace-nowrap text-[15px] font-semibold">
                {BELL_PAYMENT.amount}
              </span>
            </span>
            <span className="text-[13px] text-ink-3">{BELL_PAYMENT.time}</span>
          </span>
        </DemoStub>

        <PopoverClose asChild>
          <Link
            to="/pulse/summary"
            className="mx-3 mt-1 border-t border-line pb-1.5 pt-3 text-[15px] font-medium"
          >
            Открыть Пульс бизнеса →
          </Link>
        </PopoverClose>
      </PopoverContent>
    </Popover>
  )
}

export default NotificationsBell
