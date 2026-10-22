/** Профиль компании: `GET /api/companies/{source_id}`. */
export interface ICompanyProfile {
  /** Внешний идентификатор (source_id), не внутренний ключ БД. */
  company_id: string
  /** null вместе с name_is_placeholder — названия нет, показываем company_id. */
  name: string | null
  name_is_placeholder: boolean
  industry: string | null
  region: string | null
  /** Сумма строкой из Decimal — точность не теряется. */
  revenue: string | null
  revenue_year: number | null
  client_status: 'CLIENT' | 'PROSPECT' | 'CLOSED_CLIENT' | null
  credit_exposure: null
}
