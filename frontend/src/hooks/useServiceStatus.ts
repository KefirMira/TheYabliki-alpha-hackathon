import { useCallback, useEffect, useState } from 'react'

import { checkReadiness } from '@/shared/api/system.api'

/** Как часто перепроверяем сервис, пока вкладка открыта. */
const RECHECK_MS = 60000

/**
 * Готовность бэкенда для всей оболочки. Проверяется при входе и дальше раз
 * в минуту, пока вкладка видна, — не только пока есть проблема: иначе
 * сервер, отключившийся после успешной проверки, плашку бы не показал.
 * failureSignal — отметка неудачного фонового запроса: её смена запускает
 * проверку сразу, не дожидаясь минуты. Скрытая вкладка не опрашивает;
 * вернувшись на неё, проверяемся сразу. Ответ устаревшей проверки не
 * применяется.
 */
export const useServiceStatus = (failureSignal?: string | null) => {
  const [problem, setProblem] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)
  const [attempt, setAttempt] = useState(0)

  const recheck = useCallback(() => setAttempt((current) => current + 1), [])

  useEffect(() => {
    let stale = false
    setChecking(true)
    checkReadiness().then((result) => {
      if (stale) return
      setProblem(result)
      setChecking(false)
    })
    return () => {
      stale = true
    }
  }, [attempt])

  // Фоновый запрос не удался — проверить сервис сейчас.
  useEffect(() => {
    if (failureSignal) recheck()
  }, [failureSignal, recheck])

  useEffect(() => {
    const visible = () => document.visibilityState === 'visible'
    const timer = window.setTimeout(() => {
      if (visible()) recheck()
    }, RECHECK_MS)
    const onVisibilityChange = () => {
      if (visible()) recheck()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => {
      window.clearTimeout(timer)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [attempt, recheck])

  return { problem, checking, recheck }
}
