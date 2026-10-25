import type { ReactNode } from 'react'

/** Заголовок раздела: «Профиль компании» + подзаголовок, справа — действия. */
const PageHeading = ({
  title,
  subtitle,
  actions,
}: {
  title: string
  subtitle?: string
  actions?: ReactNode
}) => (
  <div className="flex items-center justify-between gap-6">
    <div className="flex min-w-0 flex-col gap-1">
      <h1 className="text-2xl font-bold leading-[1.2]">{title}</h1>
      {subtitle && <p className="text-sm leading-5 text-ink-2">{subtitle}</p>}
    </div>
    {actions}
  </div>
)

export default PageHeading
