import { useEffect } from 'react'

import { useAppDispatch, useAppSelector } from '@/store/hooks/redux'
import { getCompanyProfile } from '@/store/service/Company/getCompanyProfile'

/** Загружает профиль выбранной компании при старте и при её смене. */
export const useLoadCompany = () => {
  const dispatch = useAppDispatch()
  const companyId = useAppSelector((state) => state.company.currentCompanyId)

  useEffect(() => {
    if (companyId) dispatch(getCompanyProfile(companyId))
  }, [companyId, dispatch])
}
