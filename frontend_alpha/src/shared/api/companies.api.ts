import type { ICompanyProfile } from '@/store/models/ICompany'

import { apiRequest } from './request'

export const fetchCompanyProfile = (companyId: string) =>
  apiRequest<ICompanyProfile>(
    `/api/companies/${encodeURIComponent(companyId)}`,
    { method: 'GET' },
    'Не удалось загрузить профиль компании'
  )
