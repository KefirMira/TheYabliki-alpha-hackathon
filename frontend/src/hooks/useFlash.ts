import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Короткое сообщение-подтверждение («Изменения сохранены…»), которое само
 * исчезает через несколько секунд.
 */
export const useFlash = (durationMs = 3500) => {
  const [message, setMessage] = useState<string | null>(null)
  const timer = useRef<number>()

  const flash = useCallback(
    (text: string) => {
      window.clearTimeout(timer.current)
      setMessage(text)
      timer.current = window.setTimeout(() => setMessage(null), durationMs)
    },
    [durationMs]
  )

  useEffect(() => () => window.clearTimeout(timer.current), [])

  return [message, flash] as const
}
