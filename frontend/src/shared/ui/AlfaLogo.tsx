import alfaLogo from '@/assets/alfa-logo.png'
import { cn } from '@/lib/utils'

/** Знак Альфа-Банка: белая «А» с чертой на красном квадрате. */
const AlfaLogo = ({ className }: { className?: string }) => (
  <img
    src={alfaLogo}
    alt=""
    aria-hidden="true"
    className={cn('block h-8 w-8 shrink-0 rounded-[9px]', className)}
  />
)

export default AlfaLogo
