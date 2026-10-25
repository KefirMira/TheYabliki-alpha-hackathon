import { useEffect, useState } from 'react'
import { fetchCompanyProfile } from '@/shared/api/companies.api'
import { useAppSelector } from '@/store/hooks/redux'
import type { ICompanyProfile } from '@/store/models/ICompany'
// Component-local data: never reuse an actor's profile cache after logout.
export const useCompanyProfiles = (ids: string[]) => {
  const [profiles, setProfiles] = useState<
    Record<string, ICompanyProfile | null>
  >({})
  const user = useAppSelector((state) => state.auth.userId)
  const key = ids.join(',')
  useEffect(() => {
    let stale = false
    setProfiles({})
    void Promise.all(
      key
        .split(',')
        .filter(Boolean)
        .map(
          async (id) =>
            [id, await fetchCompanyProfile(id).catch(() => null)] as const
        )
    ).then((entries) => {
      if (!stale) setProfiles(Object.fromEntries(entries))
    })
    return () => {
      stale = true
    }
  }, [key, user])
  return profiles
}
