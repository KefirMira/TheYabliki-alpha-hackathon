import { Suspense } from 'react'
import { NavLink, Outlet } from 'react-router-dom'

import { cn } from '@/lib/utils'
import PageLoader from '@/shared/ui/PageLoader'

import { COMPANY_MENU } from './config'

/** Вкладка «Моя компания»: подменю слева, раздел справа. */
const CompanyLayout = () => (
  <div className="grid items-start gap-4 md:grid-cols-[240px_minmax(0,1fr)]">
    <nav
      className="flex flex-col gap-0.5 rounded-3xl bg-white p-2"
      aria-label="Разделы «Моя компания»"
    >
      {COMPANY_MENU.map(({ key, label, icon: Icon, path }) => (
        <NavLink
          key={key}
          to={path}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] transition-colors',
              isActive
                ? 'bg-surface-page font-semibold'
                : 'font-medium hover:bg-surface-page/60'
            )
          }
        >
          <Icon className="h-5 w-5 shrink-0" strokeWidth={1.8} />
          <span className="flex-1">{label}</span>
        </NavLink>
      ))}
    </nav>

    <div className="flex min-w-0 flex-col gap-4">
      <Suspense fallback={<PageLoader />}>
        <Outlet />
      </Suspense>
    </div>
  </div>
)

export default CompanyLayout
