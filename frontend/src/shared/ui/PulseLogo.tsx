import { cn } from '@/lib/utils'

interface PulseLogoProps {
  className?: string
  /** 'filled' — белая линия на красной подложке, 'mono' — линия цветом текста. */
  variant?: 'filled' | 'mono'
}

/**
 * Знак «Пульса бизнеса»: линия пульса, пик которой — буква «А» Альфы,
 * под пиком черта, как в логотипе банка.
 */
const PulseLogo = ({ className, variant = 'filled' }: PulseLogoProps) => {
  const filled = variant === 'filled'
  const stroke = filled ? '#FFFFFF' : 'currentColor'

  return (
    <svg
      viewBox="0 0 140 140"
      className={cn('h-10 w-10 shrink-0', className)}
      aria-hidden="true"
    >
      {filled && <rect width="140" height="140" rx="32" fill="#EF3124" />}
      <polyline
        points="14,74 36,74 44,62 51,74 57,74 70,24 83,92 90,74 126,74"
        fill="none"
        stroke={stroke}
        strokeWidth="11"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <rect x="54" y="104" width="32" height="11" rx="2" fill={stroke} />
    </svg>
  )
}

export default PulseLogo
