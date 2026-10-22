import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

import { cn } from '@/lib/utils'
import PulseLogo from '@/shared/ui/PulseLogo'

import CompanySwitcher from './CompanySwitcher'
import { PULSE_TABS } from './config'

/**
 * Каркас сервиса: шапка «Пульса бизнеса» с вкладками и переключателем
 * компании. Оболочка Альфа-Бизнеса (меню слева, шапка банка) — следующий шаг.
 */
const PulseLayout = ({ children }: { children: ReactNode }) => (
  <div className="min-h-screen bg-background">
    <header className="border-b border-border bg-card">
      <div className="mx-auto flex w-full max-w-[1280px] flex-wrap items-center justify-between gap-4 px-4 pt-5 md:px-8">
        <div className="flex items-center gap-3">
          <PulseLogo />
          <div>
            <p className="text-lg font-bold leading-tight">Пульс бизнеса</p>
            <p className="text-xs text-muted-foreground">в Альфа-Бизнесе</p>
          </div>
        </div>
        <CompanySwitcher />
      </div>

      <nav
        className="mx-auto flex w-full max-w-[1280px] gap-6 overflow-x-auto px-4 md:px-8"
        aria-label="Разделы Пульса"
      >
        {PULSE_TABS.map((tab) => (
          <NavLink
            key={tab.key}
            to={tab.path}
            className={({ isActive }) =>
              cn(
                'whitespace-nowrap border-b-2 py-3 text-sm font-medium transition-colors',
                isActive
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              )
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>
    </header>

    <main className="mx-auto w-full max-w-[1280px] px-4 py-6 md:px-8">
      {children}
    </main>
  </div>
)

export default PulseLayout
