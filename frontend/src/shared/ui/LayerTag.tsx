import { CircleCheck, CircleHelp } from 'lucide-react'

import { cn } from '@/lib/utils'

import AlfaLogo from './AlfaLogo'
import Tag from './Tag'

/** Слой информации в инсайте — организаторы требуют их явно разделять. */
export type InfoLayer = 'fact' | 'bank' | 'ai' | 'hyp'

/** Звезда вывода ИИ — тот же знак, что у ассистента Альфа-Бизнеса. */
export const AiStar = ({ className }: { className?: string }) => (
  <span
    className={cn('ai-star text-[13px] leading-none', className)}
    aria-hidden="true"
  >
    ✦
  </span>
)

const ICON = 'h-3 w-3'

/** Тег слоя: ФАКТ · ПОЗИЦИЯ АЛЬФА-БАНКА · ВЫВОД ИИ · ГИПОТЕЗА. */
const LayerTag = ({
  layer,
  muted = false,
}: {
  layer: InfoLayer
  /** Позиции банка нет — тег приглушён. */
  muted?: boolean
}) => {
  switch (layer) {
    case 'fact':
      return (
        <Tag tone="fact" icon={<CircleCheck className={ICON} />}>
          Факт
        </Tag>
      )
    case 'bank':
      return (
        <Tag
          tone={muted ? 'muted' : 'bank'}
          icon={
            <AlfaLogo
              className={cn(
                'h-3.5 w-3.5 rounded',
                muted && 'opacity-45 grayscale'
              )}
            />
          }
        >
          Позиция Альфа-Банка
        </Tag>
      )
    case 'ai':
      return (
        <Tag tone="ai" icon={<AiStar />}>
          Вывод ИИ
        </Tag>
      )
    case 'hyp':
      return (
        <Tag tone="hyp" icon={<CircleHelp className={ICON} />}>
          Гипотеза
        </Tag>
      )
  }
}

export default LayerTag
