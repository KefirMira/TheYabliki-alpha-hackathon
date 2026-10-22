import { ChevronDown } from 'lucide-react'

import { DEMO_COMPANY_IDS } from '@/shared/constants/companies'
import { useAppDispatch, useAppSelector } from '@/store/hooks/redux'
import { setCurrentCompany } from '@/store/reducers/CompanySlice'

/**
 * Переключатель компаний. Пока нет входа, список — демо-компании из .env;
 * после авторизации здесь будут компании, доступные по логину.
 */
const CompanySwitcher = () => {
  const dispatch = useAppDispatch()
  const { currentCompanyId, profile, loading, error } = useAppSelector(
    (state) => state.company
  )

  // Названия нет — показываем идентификатор (name_is_placeholder).
  const title = profile?.name ?? currentCompanyId ?? 'Компания не выбрана'

  return (
    <div className="flex min-w-0 items-center gap-3">
      <div className="min-w-0 text-right">
        <p className="truncate text-sm font-semibold">
          {loading && !profile ? 'Загрузка…' : title}
        </p>
        <p className="truncate text-xs text-muted-foreground">
          {error ?? profile?.industry ?? currentCompanyId}
        </p>
      </div>

      {DEMO_COMPANY_IDS.length > 1 && (
        <label className="relative">
          <span className="sr-only">Выбрать компанию</span>
          <select
            className="h-9 appearance-none rounded-xl bg-secondary py-1 pl-3 pr-8 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value={currentCompanyId ?? ''}
            onChange={(event) =>
              dispatch(setCurrentCompany(event.target.value))
            }
          >
            {DEMO_COMPANY_IDS.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
          <ChevronDown
            className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
        </label>
      )}
    </div>
  )
}

export default CompanySwitcher
