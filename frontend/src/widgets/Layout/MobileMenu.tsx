import { useEffect, useState } from 'react'
import { CircleUserRound, LogOut, Menu } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import LogoutDialog from '@/widgets/Account/LogoutDialog'

import { SidebarNav } from './AlfaSidebar'

const footerItem =
  'flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-[15px] transition-colors hover:bg-surface-chip/60'

/**
 * Меню интернет-банка на телефоне и планшете: то же, что слева на
 * десктопе, в выдвижной панели. Внизу — аккаунт и выход, которых на узком
 * экране нет в шапке. Переход по ссылке закрывает панель.
 */
const MobileMenu = () => {
  const [open, setOpen] = useState(false)
  const { pathname, search } = useLocation()

  useEffect(() => {
    setOpen(false)
  }, [pathname, search])

  // Экран стал широким (повернули планшет) — слева уже обычное меню.
  useEffect(() => {
    const wide = window.matchMedia('(min-width: 1024px)')
    const close = () => wide.matches && setOpen(false)
    wide.addEventListener('change', close)
    return () => wide.removeEventListener('change', close)
  }, [])

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        aria-label="Меню"
        className="-ml-2 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-ink transition-colors hover:bg-surface-chip lg:hidden"
      >
        <Menu className="h-6 w-6" strokeWidth={1.8} />
      </SheetTrigger>
      <SheetContent
        aria-describedby={undefined}
        className="gap-0.5 overflow-y-auto px-4 py-5"
      >
        <SheetTitle className="sr-only">Меню интернет-банка</SheetTitle>
        <SidebarNav
          footer={
            <div className="mb-2 flex flex-col gap-0.5 border-t border-line pt-3">
              <Link to="/pulse/company/account" className={footerItem}>
                <CircleUserRound
                  className="h-5 w-5 shrink-0"
                  strokeWidth={1.8}
                />
                Аккаунт и безопасность
              </Link>
              <LogoutDialog>
                <button type="button" className={footerItem}>
                  <LogOut
                    className="h-5 w-5 shrink-0 rotate-180"
                    strokeWidth={1.8}
                  />
                  Выйти
                </button>
              </LogoutDialog>
            </div>
          }
        />
      </SheetContent>
    </Sheet>
  )
}

export default MobileMenu
