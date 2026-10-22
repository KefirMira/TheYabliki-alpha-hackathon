import { Gift, LayoutGrid, Plus } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

import { cn } from '@/lib/utils'
import AlfaLogo from '@/shared/ui/AlfaLogo'
import DemoStub from '@/shared/ui/DemoStub'
import PulseLogo from '@/shared/ui/PulseLogo'
import Tag from '@/shared/ui/Tag'

import { SIDEBAR_MAIN, SIDEBAR_SERVICES, type SidebarItem } from './config'

const itemBase =
  'flex items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] transition-colors'

const itemClass = (active: boolean) =>
  cn(
    itemBase,
    active ? 'bg-surface-chip font-semibold' : 'hover:bg-surface-chip/60'
  )

/** Пункт меню: со ссылкой — раздел прототипа, без — раздел банка вне его. */
const MenuItem = ({ item, active }: { item: SidebarItem; active: boolean }) => {
  const Icon = item.icon
  const content = (
    <>
      <Icon className="h-5 w-5 shrink-0" strokeWidth={1.8} />
      <span className="flex-1">{item.label}</span>
    </>
  )
  return item.path ? (
    <Link to={item.path} className={itemClass(active)}>
      {content}
    </Link>
  ) : (
    <DemoStub label={item.label} className={itemBase}>
      {content}
    </DemoStub>
  )
}

/**
 * Левое меню Альфа-Бизнеса по статье Альфы о редизайне: светлое, тонкий
 * разделитель, сверху базовые пункты, ниже «Мои сервисы», внизу витрины.
 */
const AlfaSidebar = () => {
  const { pathname } = useLocation()
  const pulseActive = pathname.startsWith('/pulse')

  return (
    <aside className="sticky top-0 hidden h-screen flex-col gap-0.5 overflow-y-auto border-r border-line-strong px-4 py-5 lg:flex">
      <Link to="/" className="flex items-center gap-2.5 px-2 pb-[18px] pt-1">
        <AlfaLogo />
        <span className="text-lg font-bold tracking-[-0.01em]">
          Альфа-Бизнес
        </span>
      </Link>

      <DemoStub
        label="Новый платёж"
        className="mb-3 flex items-center gap-2.5 rounded-full bg-white px-4 py-2.5 text-[15px] font-medium"
      >
        <span className="flex h-[22px] w-[22px] items-center justify-center rounded-full bg-ink text-white">
          <Plus className="h-3.5 w-3.5" strokeWidth={2.5} />
        </span>
        Новый платёж
      </DemoStub>

      {SIDEBAR_MAIN.map((item) => (
        <MenuItem
          key={item.key}
          item={item}
          active={item.path === '/' && pathname === '/'}
        />
      ))}

      <div className="flex items-center justify-between px-3 pb-2 pt-5">
        <span className="text-xs font-semibold tracking-[0.08em] text-ink-3">
          МОИ СЕРВИСЫ
        </span>
        <DemoStub label="Добавить сервис" className="flex">
          <Plus className="h-4 w-4 text-ink-3" />
        </DemoStub>
      </div>

      <Link to="/pulse/summary" className={itemClass(pulseActive)}>
        <PulseLogo variant="mono" className="h-5 w-5" />
        <span className="flex-1">Пульс бизнеса</span>
        <Tag tone="info" size="sm">
          Новое
        </Tag>
      </Link>
      {SIDEBAR_SERVICES.map((item) => (
        <MenuItem key={item.key} item={item} active={false} />
      ))}

      <div className="min-h-6 flex-1" />

      <div className="flex flex-col gap-2 border-t border-line pt-3">
        <DemoStub
          label="Кэшбэк и привилегии"
          className="flex items-center gap-3 rounded-xl px-3 py-2 text-[15px]"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-tone-peach text-[#E2562F]">
            <Gift className="h-4 w-4" />
          </span>
          Кэшбэк и привилегии
        </DemoStub>
        <DemoStub
          label="Все сервисы и продукты"
          className="flex items-center gap-3 rounded-xl px-3 py-2 text-[15px]"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-tone-info text-tone-info-fg">
            <LayoutGrid className="h-4 w-4" />
          </span>
          Все сервисы и продукты
        </DemoStub>
      </div>
    </aside>
  )
}

export default AlfaSidebar
