import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

import { TAG_TONES, type TagTone } from './tagTones'

interface TagProps {
  tone: TagTone
  icon?: ReactNode
  /** sm — мелкий бейдж в меню («НОВОЕ»). */
  size?: 'md' | 'sm'
  className?: string
  children: ReactNode
}

/** Тег мелким капсом на тонированной подложке — общий для всех экранов. */
const Tag = ({ tone, icon, size = 'md', className, children }: TagProps) => (
  <span
    className={cn(
      'inline-flex items-center gap-[5px] whitespace-nowrap rounded-md font-bold uppercase leading-[14px] tracking-[0.06em]',
      size === 'md' ? 'text-[11px]' : 'text-[10px]',
      size === 'sm'
        ? 'px-1.5 py-[3px]'
        : icon
          ? 'py-1 pl-1.5 pr-2'
          : 'px-2 py-1',
      TAG_TONES[tone],
      className
    )}
  >
    {icon}
    {children}
  </span>
)

export default Tag
