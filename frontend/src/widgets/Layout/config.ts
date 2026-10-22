import {
  ArrowLeftRight,
  Building2,
  CircleUserRound,
  CreditCard,
  FileText,
  Globe,
  House,
  IdCard,
  Layers,
  type LucideIcon,
  Percent,
  SlidersHorizontal,
  Users,
} from 'lucide-react'

/** Пункт левого меню Альфа-Бизнеса. Без path — раздел банка вне прототипа. */
export interface SidebarItem {
  key: string
  label: string
  icon: LucideIcon
  path?: string
}

export const SIDEBAR_MAIN: readonly SidebarItem[] = [
  { key: 'home', label: 'Главная', icon: House, path: '/' },
  { key: 'payments', label: 'Платежи', icon: ArrowLeftRight },
  { key: 'accounts', label: 'Счета', icon: CreditCard },
  { key: 'counterparties', label: 'Контрагенты', icon: Users },
  { key: 'credits', label: 'Кредиты', icon: Percent },
  { key: 'documents', label: 'Документы', icon: FileText },
]

/** «Мои сервисы» — Пульс рисуется отдельно, со своим знаком и бейджем. */
export const SIDEBAR_SERVICES: readonly SidebarItem[] = [
  { key: 'ved', label: 'ВЭД', icon: Globe },
  { key: 'salary', label: 'Зарплатный проект', icon: IdCard },
]

/** Вкладка сервиса «Пульс бизнеса». */
export interface PulseTab {
  key: string
  label: string
  path: string
  /** Префиксы адресов, на которых вкладка активна. */
  match: string[]
}

export const PULSE_TABS: readonly PulseTab[] = [
  {
    key: 'summary',
    label: 'Сводка',
    path: '/pulse/summary',
    match: ['/pulse/summary', '/pulse/sources'],
  },
  {
    key: 'insights',
    label: 'Инсайты',
    path: '/pulse/insights',
    match: ['/pulse/insights'],
  },
  {
    key: 'company',
    label: 'Моя компания',
    path: '/pulse/company/profile',
    match: ['/pulse/company'],
  },
]

/** Подменю вкладки «Моя компания». */
export const COMPANY_MENU: readonly SidebarItem[] = [
  {
    key: 'profile',
    label: 'Профиль компании',
    icon: Building2,
    path: '/pulse/company/profile',
  },
  {
    key: 'context',
    label: 'Контекст',
    icon: Layers,
    path: '/pulse/company/context',
  },
  {
    key: 'settings',
    label: 'Настройки Пульса',
    icon: SlidersHorizontal,
    path: '/pulse/company/settings',
  },
  {
    key: 'account',
    label: 'Аккаунт и безопасность',
    icon: CircleUserRound,
    path: '/pulse/company/account',
  },
]
