import { useCallback, useEffect, useState } from 'react'

import {
  aiAvailability,
  fetchReadiness,
  type IReadiness,
} from '@/shared/api/system.api'

/**
 * Готовность бэкенда для экрана: результат `/ready` и доступность ИИ.
 * Ошибка не ломает экран — доступность ИИ тогда «неизвестна», и решение
 * остаётся за ответом самого бэкенда.
 */
export const useReadiness = () => {
  const [readiness, setReadiness] = useState<IReadiness | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let stale = false
    setLoading(true)
    fetchReadiness()
      .then((result) => {
        if (stale) return
        setReadiness(result)
        setError(null)
      })
      .catch((reason: Error) => {
        if (stale) return
        setReadiness(null)
        setError(reason.message)
      })
      .finally(() => {
        if (!stale) setLoading(false)
      })
    return () => {
      stale = true
    }
  }, [attempt])

  const reload = useCallback(() => setAttempt((current) => current + 1), [])

  return {
    readiness,
    error,
    loading,
    ai: aiAvailability(readiness),
    reload,
  }
}
