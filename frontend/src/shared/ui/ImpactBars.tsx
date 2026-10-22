import { cn } from '@/lib/utils'
import type { ImpactLevel } from '@/store/models/IPulse'

/** Три полоски уровня влияния: закрашено столько, каков уровень. */
const ImpactBars = ({ level }: { level: ImpactLevel }) => (
  <span className="flex gap-0.5" aria-hidden="true">
    {[1, 2, 3].map((bar) => (
      <span
        key={bar}
        className={cn(
          'h-1 w-3 rounded-sm',
          bar <= level ? 'bg-ink' : 'bg-surface-off'
        )}
      />
    ))}
  </span>
)

export default ImpactBars
