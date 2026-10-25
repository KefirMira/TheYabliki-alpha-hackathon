import { ChevronLeft } from 'lucide-react'
import { Link } from 'react-router-dom'

/** «‹ Все инсайты», «‹ Сводка» — возврат на родительский экран. */
const BackLink = ({ to, children }: { to: string; children: string }) => (
  <Link
    to={to}
    className="inline-flex items-center gap-1.5 self-start rounded-xl py-2 pl-2 pr-3 text-[15px] font-medium transition-colors hover:bg-surface-chip"
  >
    <ChevronLeft className="h-[18px] w-[18px]" />
    {children}
  </Link>
)

export default BackLink
