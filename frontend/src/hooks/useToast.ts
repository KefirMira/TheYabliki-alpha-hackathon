import { useEffect, useState } from 'react'

import { TOAST_ANIMATION_DURATION, TOAST_LIMIT } from '@/shared/constants/toast'

export type ToastVariant = 'success' | 'info' | 'error'

export interface ToasterToast {
  id: string
  message: string
  variant: ToastVariant
  /** false — идёт анимация закрытия, после неё тост удаляется. */
  open: boolean
}

type Action =
  | { type: 'ADD'; toast: ToasterToast }
  | { type: 'DISMISS'; id: string }
  | { type: 'REMOVE'; id: string }

interface State {
  toasts: ToasterToast[]
}

/**
 * Стор тостов вне React, как в shadcn: показать тост можно из любого места
 * (обработчик, thunk), а Toaster подписан на изменения. Жизненный цикл:
 * ADD (open) → DISMISS (анимация закрытия) → через TOAST_ANIMATION_DURATION
 * REMOVE. Время показа отсчитывает Radix: он ставит таймер на паузу, пока
 * курсор над тостом или окно не в фокусе.
 */
let memoryState: State = { toasts: [] }
const listeners = new Set<(state: State) => void>()
const removeTimers = new Map<string, ReturnType<typeof setTimeout>>()
let count = 0

export const reducer = (state: State, action: Action): State => {
  switch (action.type) {
    case 'ADD':
      return {
        toasts: [action.toast, ...state.toasts].slice(0, TOAST_LIMIT),
      }
    case 'DISMISS':
      return {
        toasts: state.toasts.map((toast) =>
          toast.id === action.id ? { ...toast, open: false } : toast
        ),
      }
    case 'REMOVE':
      return {
        toasts: state.toasts.filter((toast) => toast.id !== action.id),
      }
  }
}

const dispatch = (action: Action) => {
  memoryState = reducer(memoryState, action)
  listeners.forEach((listener) => listener(memoryState))
}

/** Закрыть тост: сначала анимация, затем удаление из списка. */
export const dismissToast = (id: string) => {
  if (removeTimers.has(id)) return
  dispatch({ type: 'DISMISS', id })
  removeTimers.set(
    id,
    setTimeout(() => {
      removeTimers.delete(id)
      dispatch({ type: 'REMOVE', id })
    }, TOAST_ANIMATION_DURATION)
  )
}

export const showToast = (message: string, variant: ToastVariant) => {
  count = (count + 1) % Number.MAX_SAFE_INTEGER
  const id = String(count)
  dispatch({ type: 'ADD', toast: { id, message, variant, open: true } })
  return id
}

export const useToastState = () => {
  const [state, setState] = useState(memoryState)

  useEffect(() => {
    listeners.add(setState)
    return () => {
      listeners.delete(setState)
    }
  }, [])

  return state
}
