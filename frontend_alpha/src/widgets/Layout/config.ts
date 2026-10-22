/** Вкладка сервиса «Пульс бизнеса». */
export interface PulseTabItem {
  key: string
  label: string
  path: string
}

export const PULSE_TABS: readonly PulseTabItem[] = [
  { key: 'summary', label: 'Сводка', path: '/summary' },
  { key: 'insights', label: 'Инсайты', path: '/insights' },
  { key: 'company', label: 'Моя компания', path: '/company' },
] as const
