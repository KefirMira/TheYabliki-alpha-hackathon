import { companyProfileFields } from '@/shared/api/mappers/companyMappers'
import Card from '@/shared/ui/Card'
import type { ICompanyProfile } from '@/store/models/ICompany'

/**
 * «Данные компании»: поля профиля из API с источником. Изменить их пока
 * нельзя — API профиля только на чтение.
 */
const CompanyFields = ({ profile }: { profile: ICompanyProfile }) => {
  const fields = companyProfileFields(profile)

  return (
    <Card>
      <h2 className="text-[17px] font-semibold leading-6">Данные компании</h2>

      {fields.length === 0 ? (
        <p className="text-[15px] text-ink-2">
          В сохранённом профиле пока нет сведений о компании.
        </p>
      ) : (
        <div className="grid gap-2.5 md:grid-cols-2">
          {fields.map((field) => (
            <div
              key={field.key}
              className="flex min-w-0 flex-col gap-1.5 rounded-2xl bg-surface-cell px-4 py-3.5"
            >
              <span className="text-xs font-semibold uppercase tracking-[0.06em] text-ink-3">
                {field.label}
              </span>
              <span className="text-base font-medium leading-6">
                {field.value}
              </span>
              <span className="flex items-center gap-1.5 text-xs font-medium text-ink-3">
                <span className="h-1.5 w-1.5 rounded-full bg-current" />
                Из сохранённого профиля; источник не подтверждён
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

export default CompanyFields
