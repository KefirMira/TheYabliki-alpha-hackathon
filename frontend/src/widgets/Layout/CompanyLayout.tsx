import { Suspense, useEffect, useRef } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { cn } from '@/lib/utils'
import PageLoader from '@/shared/ui/PageLoader'

import { COMPANY_MENU } from './config'

/**
 * Вкладка «Моя компания»: подменю слева, раздел справа. На узком экране
 * подменю — горизонтальная полоса над разделом, листается вбок.
 */
const CompanyLayout = () => {
  const navRef = useRef<HTMLElement>(null)
  const { pathname } = useLocation()

  // Полоса на узком экране: активный пункт не должен прятаться за краем.
  useEffect(() => {
    const nav = navRef.current
    const active = nav?.querySelector<HTMLElement>('[aria-current="page"]')
    if (!nav || !active || nav.scrollWidth <= nav.clientWidth) return
    nav.scrollTo({
      left: active.offsetLeft - (nav.clientWidth - active.offsetWidth) / 2,
      behavior: 'smooth',
    })
  }, [pathname])

  return (
    <div className="grid items-start gap-4 md:grid-cols-[240px_minmax(0,1fr)]">
      <nav
        ref={navRef}
        className="scroll-x-quiet -mx-4 flex gap-1.5 px-4 md:mx-0 md:flex-col md:gap-0.5 md:rounded-3xl md:bg-white md:p-2"
        aria-label="Разделы «Моя компания»"
      >
        {COMPANY_MENU.map(({ key, label, icon: Icon, path }) => (
          <NavLink
            key={key}
            to={path}
            className={({ isActive }) =>
              cn(
                'flex shrink-0 items-center gap-2 whitespace-nowrap rounded-xl md:whitespace-normal px-3 py-2 text-[15px] transition-colors md:gap-3 md:py-2.5',
                isActive
                  ? 'bg-ink font-semibold text-white md:bg-surface-page md:text-ink'
                  : 'bg-white font-medium md:bg-transparent md:hover:bg-surface-page/60'
              )
            }
          >
            <Icon
              className="h-[18px] w-[18px] shrink-0 md:h-5 md:w-5"
              strokeWidth={1.8}
            />
            <span className="md:flex-1">{label}</span>
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
}

export default CompanyLayout
