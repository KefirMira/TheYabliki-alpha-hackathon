import { useEffect, useState } from 'react'

import { fetchCompanyProfile } from '@/shared/api/companies.api'
import type { ICompanyProfile } from '@/store/models/ICompany'

// Профили компаний логина меняются редко — один запрос на компанию за сессию.
const cache = new Map<string, Promise<ICompanyProfile | null>>()

const loadProfile = (id: string) => {
  if (!cache.has(id)) {
    cache.set(
      id,
      fetchCompanyProfile(id).catch(() => {
        // Ошибку не кешируем: при следующем открытии меню попробуем снова.
        cache.delete(id)
        return null
      })
    )
  }
  return cache.get(id)!
}

/**
 * Профили нескольких компаний — для переключателя в шапке: вместо
 * идентификатора показать название и отрасль. Нет ответа — остаётся id.
 */
export const useCompanyProfiles = (ids: string[]) => {
  const [profiles, setProfiles] = useState<
    Record<string, ICompanyProfile | null>
  >({})
  const key = ids.join(',')

  useEffect(() => {
    let stale = false
    Promise.all(
      key
        .split(',')
        .filter(Boolean)
        .map(async (id) => [id, await loadProfile(id)] as const)
    ).then((entries) => {
      if (!stale) setProfiles(Object.fromEntries(entries))
    })
    return () => {
      stale = true
    }
  }, [key])

  return profiles
}
