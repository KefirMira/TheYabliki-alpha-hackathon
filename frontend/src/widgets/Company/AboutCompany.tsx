import { companyNameOf } from '@/shared/api/mappers/companyMappers'
import Card from '@/shared/ui/Card'
import type { ICompanyProfile } from '@/store/models/ICompany'

/**
 * «О компании»: название из профиля банка. Описания бизнеса в API нет —
 * блок описания не показываем, а не подставляем черновик.
 */
const AboutCompany = ({ profile }: { profile: ICompanyProfile }) => (
  <Card>
    <h2 className="text-[17px] font-semibold leading-6">О компании</h2>
    <div className="flex flex-col gap-1">
      <span className="text-[22px] font-bold leading-[1.2]">
        {companyNameOf(profile)}
      </span>
      <span className="text-[13px] text-ink-3">
        {profile.name_is_placeholder
          ? 'Название в данных банка не указано'
          : `Идентификатор ${profile.company_id}`}
      </span>
    </div>
  </Card>
)

export default AboutCompany
