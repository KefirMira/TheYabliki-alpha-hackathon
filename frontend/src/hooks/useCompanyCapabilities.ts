import { useEffect, useState } from 'react'
import { apiRequest } from '@/shared/api/request'
import { useAppSelector } from '@/store/hooks/redux'
interface Capabilities {
  company_id: string
  mode: 'demo' | 'full'
  operations: {
    analyze_new: {
      state: 'AVAILABLE' | 'BLOCKED' | 'UNAVAILABLE' | 'UNKNOWN'
      reasons: { code: string }[]
    }
  }
}
export const useCompanyCapabilities = (company: string | null) => {
  const user = useAppSelector((state) => state.auth.userId)
  const [value, setValue] = useState<{
    actor: string | null
    data: Capabilities
  } | null>(null)
  useEffect(() => {
    let stale = false
    setValue(null)
    if (company)
      void apiRequest<Capabilities>(
        `/api/companies/${encodeURIComponent(company)}/capabilities`,
        { method: 'GET' },
        'Не удалось проверить доступность анализа'
      )
        .then((v) => {
          if (!stale) setValue({ actor: user, data: v })
        })
        .catch(() => {
          if (!stale) setValue(null)
        })
    return () => {
      stale = true
    }
  }, [company, user])
  // Check identity as well: a previous company's AVAILABLE must not flash on switch.
  const operation =
    value?.actor === user && value?.data.company_id === company
      ? value.data.operations.analyze_new
      : null
  return {
    blocked: operation?.state !== 'AVAILABLE',
    state: operation?.state ?? 'UNKNOWN',
    reasons: operation?.reasons.map((r) => r.code) ?? [],
  }
}
