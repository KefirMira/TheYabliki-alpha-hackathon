import {
  CalendarDays,
  Check,
  ChevronDown,
  LogOut,
  MessageSquare,
  Search,
  User,
} from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

import {
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { cn } from '@/lib/utils'
import { DEMO_COMPANY_IDS } from '@/shared/constants/companies'
import BackLink from '@/shared/ui/BackLink'
import DemoStub from '@/shared/ui/DemoStub'
import { useAppDispatch, useAppSelector } from '@/store/hooks/redux'
import { setCurrentCompany } from '@/store/reducers/CompanySlice'
import { selectCompanyTitle } from '@/store/selectors/pulse'
import LogoutDialog from '@/widgets/Account/LogoutDialog'

import NotificationsBell from './NotificationsBell'

const iconBase =
  'flex h-10 w-10 items-center justify-center rounded-xl text-ink-2'

const iconButton = cn(iconBase, 'transition-colors hover:bg-surface-chip')

const Divider = () => <span className="mx-1.5 h-6 w-px bg-line-strong" />

/**
 * Организация в шапке. Компании определяются по логину; пока нет
 * авторизации, это демо-компании бэкенда из VITE_DEMO_COMPANY_IDS.
 */
const CompanyMenu = () => {
  const dispatch = useAppDispatch()
  const title = useAppSelector(selectCompanyTitle)
  const { currentCompanyId, loading, profile } = useAppSelector(
    (state) => state.company
  )
  const username = useAppSelector((state) => state.auth.username)

  return (
    <Popover>
      <PopoverTrigger className="flex items-center gap-2 rounded-xl px-3 py-1.5 text-left transition-colors hover:bg-surface-chip data-[state=open]:bg-surface-chip">
        <span className="flex flex-col gap-0.5">
          <span className="max-w-[260px] truncate text-[15px] font-semibold">
            {loading && !profile ? 'Загрузка…' : title}
          </span>
          <span className="text-[13px] text-ink-3">{username ?? 'Гость'}</span>
        </span>
        {DEMO_COMPANY_IDS.length > 1 && (
          <ChevronDown className="h-4 w-4 text-ink-3" />
        )}
      </PopoverTrigger>
      {DEMO_COMPANY_IDS.length > 1 && (
        <PopoverContent className="flex w-72 flex-col">
          <span className="px-3 pb-1.5 pt-2 text-xs font-semibold tracking-[0.06em] text-ink-3">
            КОМПАНИИ ПО ВАШЕМУ ЛОГИНУ
          </span>
          {DEMO_COMPANY_IDS.map((id) => {
            const active = id === currentCompanyId
            return (
              <PopoverClose
                key={id}
                onClick={() => !active && dispatch(setCurrentCompany(id))}
                className={cn(
                  'flex items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left text-[15px] transition-colors hover:bg-surface-page',
                  active && 'font-semibold'
                )}
              >
                <span className="flex min-w-0 flex-col">
                  <span className="truncate">{active ? title : id}</span>
                  {active && (
                    <span className="text-xs font-normal text-ink-3">{id}</span>
                  )}
                </span>
                {active && <Check className="h-4 w-4 shrink-0" />}
              </PopoverClose>
            )
          })}
        </PopoverContent>
      )}
    </Popover>
  )
}

/**
 * Шапка интернет-банка: поиск, календарь, чат, уведомления, организация.
 * Внутри Пульса слева — возврат на главную банка.
 */
const AlfaHeader = () => {
  const inPulse = useLocation().pathname.startsWith('/pulse')

  return (
    <header className="flex h-[72px] items-center justify-end gap-1.5 px-4 lg:pl-10 lg:pr-8">
      {inPulse && (
        <div className="-ml-2 mr-auto flex">
          <BackLink to="/">На главную</BackLink>
        </div>
      )}
      <DemoStub
        label="Поиск"
        className="flex items-center gap-2 px-3 py-2 text-[15px] text-ink-3"
      >
        <Search className="h-5 w-5" strokeWidth={1.8} />
        Поиск
      </DemoStub>
      <Divider />
      <DemoStub label="Календарь платежей" className={iconBase}>
        <CalendarDays className="h-5 w-5" strokeWidth={1.8} />
      </DemoStub>
      <DemoStub label="Чат с банком" className={iconBase}>
        <MessageSquare className="h-5 w-5" strokeWidth={1.8} />
      </DemoStub>
      <NotificationsBell />
      <Divider />
      <CompanyMenu />
      <Link
        to="/pulse/company/account"
        className={iconButton}
        aria-label="Аккаунт и безопасность"
      >
        <User className="h-5 w-5" strokeWidth={1.8} />
      </Link>
      <LogoutDialog>
        <button type="button" className={iconButton} aria-label="Выйти">
          <LogOut className="h-5 w-5 rotate-180" strokeWidth={1.8} />
        </button>
      </LogoutDialog>
    </header>
  )
}

export default AlfaHeader
