import { Suspense } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'

import { cn } from '@/lib/utils'
import PageLoader from '@/shared/ui/PageLoader'
import PulseLogo from '@/shared/ui/PulseLogo'

import { PULSE_TABS } from './config'

/** Шапка сервиса «Пульс бизнеса» и вкладки Сводка · Инсайты · Моя компания. */
const PulseLayout = () => {
  const { pathname } = useLocation()

  return (
    <>
      <div className="flex flex-col gap-3">
        <div className="flex min-h-10 items-center gap-3">
          <PulseLogo />
          <span className="flex flex-col gap-px">
            <span className="text-[22px] font-bold leading-[1.15]">
              Пульс бизнеса
            </span>
            <span className="text-[13px] text-ink-3">в Альфа-Бизнесе</span>
          </span>
        </div>

        <nav
          className="scroll-x-quiet flex gap-7 border-b border-line-strong text-[15px]"
          aria-label="Разделы Пульса"
        >
          {PULSE_TABS.map((tab) => {
            const active = tab.match.some((prefix) =>
              pathname.startsWith(prefix)
            )
            return (
              <Link
                key={tab.key}
                to={tab.path}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  '-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 pb-3 pt-1.5 transition-colors',
                  active
                    ? 'border-ink font-semibold text-ink'
                    : 'border-transparent font-medium text-ink-2 hover:text-ink'
                )}
              >
                {tab.label}
              </Link>
            )
          })}
        </nav>
      </div>

      <Suspense fallback={<PageLoader />}>
        <Outlet />
      </Suspense>
    </>
  )
}

export default PulseLayout
