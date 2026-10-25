/**
 * Компании для переключателя, пока нет авторизации: source_id из
 * VITE_DEMO_COMPANY_IDS. После входа список будет приходить по логину.
 */
export const DEMO_COMPANY_IDS: string[] = (
  import.meta.env.VITE_DEMO_COMPANY_IDS ?? ''
)
  .split(',')
  .map((id) => id.trim())
  .filter(Boolean)
