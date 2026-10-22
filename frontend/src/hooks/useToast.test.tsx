import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { Toaster } from '@/components/ui/toaster'
import {
  TOAST_ANIMATION_DURATION,
  TOAST_DURATION,
} from '@/shared/constants/toast'
import { toast } from '@/shared/ui/appToast'

describe('тосты', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('новый тост заменяет прежний: на экране один', () => {
    render(<Toaster />)

    act(() => {
      toast.success('Первый')
      toast.info('Второй')
    })

    expect(screen.queryByText('Первый')).toBeNull()
    expect(screen.getByText('Второй')).toBeInTheDocument()
  })

  it('исчезает сам после показа и анимации закрытия', () => {
    render(<Toaster />)

    act(() => {
      toast.success('Сохранено')
    })
    expect(screen.getByText('Сохранено')).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(TOAST_DURATION + TOAST_ANIMATION_DURATION + 50)
    })

    expect(screen.queryByText('Сохранено')).toBeNull()
  })

  it('закрывается крестиком', () => {
    render(<Toaster />)

    act(() => {
      toast.error('Ошибка')
    })
    fireEvent.click(screen.getByRole('button', { name: 'Закрыть' }))
    act(() => {
      vi.advanceTimersByTime(TOAST_ANIMATION_DURATION + 50)
    })

    expect(screen.queryByText('Ошибка')).toBeNull()
  })
})
