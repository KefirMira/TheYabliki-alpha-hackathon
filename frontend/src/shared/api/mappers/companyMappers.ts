import type { ICompanyProfile } from '@/store/models/ICompany'

/** Поле профиля компании для экрана: подпись и значение из API. */
export interface ICompanyProfileField {
  key: string
  label: string
  value: string
}

const CLIENT_STATUS_LABEL: Record<
  NonNullable<ICompanyProfile['client_status']>,
  string
> = {
  CLIENT: 'Клиент банка',
  PROSPECT: 'Потенциальный клиент',
  CLOSED_CLIENT: 'Бывший клиент',
}

/**
 * Выручка из Decimal-строки: разряды через неразрывный пробел, без перевода
 * в number — точность суммы не теряется. Копейки «.00» не показываем.
 */
export const formatRevenue = (revenue: string) => {
  const [integer, fraction] = revenue.trim().split('.')
  const sign = integer.startsWith('-') ? '−' : ''
  const digits = integer.replace(/^-/, '')
  if (!/^\d+$/.test(digits)) return revenue
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, '\u00A0')
  const cents = fraction && /[1-9]/.test(fraction) ? `,${fraction}` : ''
  return `${sign}${grouped}${cents}\u00A0₽`
}

/** Название для экрана: без названия в API — идентификатор компании. */
export const companyNameOf = (profile: ICompanyProfile) =>
  profile.name ?? profile.company_id

/** Поля профиля из API. Пустые (null) не показываем — ничего не дописываем. */
export const companyProfileFields = (
  profile: ICompanyProfile
): ICompanyProfileField[] => {
  const fields: (ICompanyProfileField | null)[] = [
    profile.industry && {
      key: 'industry',
      label: 'Отрасль',
      value: profile.industry,
    },
    profile.region && { key: 'region', label: 'Регион', value: profile.region },
    profile.revenue && {
      key: 'revenue',
      label: profile.revenue_year
        ? `Выручка за ${profile.revenue_year} год`
        : 'Выручка',
      value: formatRevenue(profile.revenue),
    },
    profile.client_status && {
      key: 'client_status',
      label: 'Статус',
      value: CLIENT_STATUS_LABEL[profile.client_status],
    },
  ]
  return fields.filter(Boolean)
}
