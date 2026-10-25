import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { checkReadiness } from '@/shared/api/system.api'

import { useServiceStatus } from './useServiceStatus'

vi.mock('@/shared/api/system.api', () => ({
  checkReadiness: vi.fn(),
}))

const DOWN = 'Сервер Пульса не отвечает. Попробуйте позже'

/** Дать промису проверки разрешиться внутри act. */
const flush = () => act(async () => {})

describe('useServiceStatus', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.mocked(checkReadiness).mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('замечает отключение сервера после успешной проверки', async () => {
    vi.mocked(checkReadiness)
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(DOWN)
    const { result } = renderHook(() => useServiceStatus())
    await flush()
    expect(result.current.problem).toBeNull()

    await act(async () => {
      vi.advanceTimersByTime(60000)
    })
    await flush()

    expect(result.current.problem).toBe(DOWN)
  })

  it('неудачный фоновый запрос запускает проверку сразу', async () => {
    vi.mocked(checkReadiness)
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(DOWN)
    const { result, rerender } = renderHook(
      ({ failedAt }) => useServiceStatus(failedAt),
      { initialProps: { failedAt: null as string | null } }
    )
    await flush()

    rerender({ failedAt: '2026-10-24T12:00:00Z' })
    await flush()

    expect(checkReadiness).toHaveBeenCalledTimes(2)
    expect(result.current.problem).toBe(DOWN)
  })
})
