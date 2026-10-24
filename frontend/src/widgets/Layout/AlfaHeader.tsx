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
import { useCompanyProfiles } from '@/hooks/useCompanyProfiles'
import { cn } from '@/lib/utils'
import { companyNameOf } from '@/shared/api/mappers/companyMappers'
import BackLink from '@/shared/ui/BackLink'
import DemoStub from '@/shared/ui/DemoStub'
import { useAppDispatch, useAppSelector } from '@/store/hooks/redux'
import { setCurrentCompany } from '@/store/reducers/CompanySlice'
import {
  selectCompanyTitle,
  selectUserCompanyIds,
} from '@/store/selectors/pulse'
import LogoutDialog from '@/widgets/Account/LogoutDialog'

import MobileMenu from './MobileMenu'
import NotificationsBell from './NotificationsBell'

const iconBase =
  'flex h-10 w-10 items-center justify-center rounded-xl text-ink-2'

const iconButton = cn(iconBase, 'transition-colors hover:bg-surface-chip')

const Divider = ({ className }: { className?: string }) => (
  <span className={cn('mx-1.5 h-6 w-px shrink-0 bg-line-strong', className)} />
)

/**
 * Организация в шапке. Компании определяются по логину: пока нет
 * авторизации — по тестовым учёткам сборки (VITE_DEMO_ACCOUNTS).
 */
const CompanyMenu = () => {
  const dispatch = useAppDispatch()
  const title = useAppSelector(selectCompanyTitle)
  const { currentCompanyId, loading, profile } = useAppSelector(
    (state) => state.company
  )
  const username = useAppSelector((state) => state.auth.username)
  const companyIds = useAppSelector(selectUserCompanyIds)
  // Названия и отрасли остальных компаний — вместо голых идентификаторов.
  const profiles = useCompanyProfiles(companyIds.length > 1 ? companyIds : [])

  return (
    <Popover>
      <PopoverTrigger className="flex min-w-0 items-center gap-1.5 rounded-xl px-2 py-1.5 text-left transition-colors hover:bg-surface-chip data-[state=open]:bg-surface-chip sm:gap-2 sm:px-3">
        <span className="flex min-w-0 flex-col gap-0.5">
          <span className="max-w-[150px] truncate text-[15px] font-semibold sm:max-w-[260px]">
            {loading && !profile ? 'Загрузка…' : title}
          </span>
          <span className="truncate text-[13px] text-ink-3">
            {username ?? 'Гость'}
          </span>
        </span>
        {companyIds.length > 1 && (
          <ChevronDown className="h-4 w-4 shrink-0 text-ink-3" />
        )}
      </PopoverTrigger>
      {companyIds.length > 1 && (
        <PopoverContent
          collisionPadding={16}
          className="flex w-[min(288px,calc(100vw-32px))] flex-col"
        >
          <span className="px-3 pb-1.5 pt-2 text-xs font-semibold tracking-[0.06em] text-ink-3">
            КОМПАНИИ ПО ВАШЕМУ ЛОГИНУ
          </span>
          {companyIds.map((id) => {
            const active = id === currentCompanyId
            const known = profiles[id]
            const name = active ? title : known ? companyNameOf(known) : id
            const details = known
              ? [known.industry, known.region].filter(Boolean).join(' · ')
              : ''
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
                  <span className="truncate">{name}</span>
                  <span className="truncate text-xs font-normal text-ink-3">
                    {details || id}
                  </span>
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
    <header className="flex h-16 items-center gap-1 px-4 lg:h-[72px] lg:gap-1.5 lg:pl-10 lg:pr-8">
      {/* Узкий экран: кнопка меню вместо левого меню. */}
      <MobileMenu />
      {inPulse && (
        <div className="-ml-2 hidden lg:flex">
          <BackLink to="/">На главную</BackLink>
        </div>
      )}
      <span className="flex-1" />
      <DemoStub
        label="Поиск"
        className="hidden items-center gap-2 px-3 py-2 text-[15px] text-ink-3 md:flex"
      >
        <Search className="h-5 w-5" strokeWidth={1.8} />
        Поиск
      </DemoStub>
      <Divider className="hidden md:block" />
      <DemoStub
        label="Календарь платежей"
        className={cn(iconBase, 'hidden md:flex')}
      >
        <CalendarDays className="h-5 w-5" strokeWidth={1.8} />
      </DemoStub>
      <DemoStub label="Чат с банком" className={cn(iconBase, 'hidden md:flex')}>
        <MessageSquare className="h-5 w-5" strokeWidth={1.8} />
      </DemoStub>
      <NotificationsBell />
      <Divider className="hidden sm:block" />
      <CompanyMenu />
      {/* Аккаунт и выход на телефоне — в меню. */}
      <Link
        to="/pulse/company/account"
        className={cn(iconButton, 'hidden sm:flex')}
        aria-label="Аккаунт и безопасность"
      >
        <User className="h-5 w-5" strokeWidth={1.8} />
      </Link>
      <LogoutDialog>
        <button
          type="button"
          className={cn(iconButton, 'hidden sm:flex')}
          aria-label="Выйти"
        >
          <LogOut className="h-5 w-5 rotate-180" strokeWidth={1.8} />
        </button>
      </LogoutDialog>
    </header>
  )
}

export default AlfaHeader
