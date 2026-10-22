import {
  humanizeApiError,
  REQUEST_TIMEOUT_MESSAGE,
  SERVER_UNREACHABLE_MESSAGE,
} from './apiErrors'

const BASE = () => import.meta.env.VITE_BASE_API
/** Таймаут по умолчанию; анализ новости через LLM передаёт свой. */
export const DEFAULT_TIMEOUT_MS = 20000

/**
 * Ошибка API. `code` — стабильный код бэкенда (`COMPANY_NOT_FOUND`…) или
 * свой: `TIMEOUT` и `NETWORK`, когда ответа нет. Текст — для показа.
 */
export class ApiError extends Error {
  status: number
  code: string | null

  constructor(message: string, status: number, code: string | null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

const codeOf = (body: unknown): string | null => {
  const detail = (body as { detail?: unknown } | null)?.detail
  // 422 FastAPI присылает detail массивом — кода там нет.
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const code = (detail as { code?: unknown }).code
    return typeof code === 'string' ? code : null
  }
  return null
}

/**
 * Запрос к API бэкенда: базовый адрес, таймаут (действует и на чтение тела),
 * разбор ошибок в ApiError с русским текстом.
 *
 * Повторов здесь нет намеренно: POST анализа не идемпотентен, повтор
 * создал бы второй запуск и второй вызов LLM.
 */
export const apiRequest = async <T>(
  path: string,
  init: RequestInit,
  fallback: string,
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<T> => {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(`${BASE()}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...init.headers,
      },
    })

    if (!response.ok) {
      // null — только когда тело не JSON. Таймаут при чтении тела
      // пробрасываем дальше, иначе он превратился бы в общую ошибку.
      const body = await response.json().catch((error) => {
        if (error?.name === 'AbortError') throw error
        return null
      })
      const code = codeOf(body)
      throw new ApiError(
        humanizeApiError(code, fallback),
        response.status,
        code
      )
    }

    return (await response.json()) as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error?.name === 'AbortError') {
      throw new ApiError(REQUEST_TIMEOUT_MESSAGE, 0, 'TIMEOUT')
    }
    throw new ApiError(SERVER_UNREACHABLE_MESSAGE, 0, 'NETWORK')
  } finally {
    clearTimeout(timeoutId)
  }
}
