import {
  Banknote,
  Droplet,
  Globe,
  Landmark,
  type LucideIcon,
  Percent,
  Users,
} from 'lucide-react'

import type { PulseFactor } from '@/store/models/IPulse'

/** Иконка фактора влияния — в сводке и фильтрах ленты. */
export const FACTOR_ICONS: Record<PulseFactor, LucideIcon> = {
  rate: Percent,
  fuel: Droplet,
  cp: Users,
  dem: Landmark,
  reg: Globe,
  fx: Banknote,
}
