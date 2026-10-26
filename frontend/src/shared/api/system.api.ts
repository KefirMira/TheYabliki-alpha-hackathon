import { ApiError, apiRequest } from './request'

/** Ответ `GET /ready` (docs/API_CONTRACT.md). */
export interface IReadiness {
  status: 'ready' | 'not_ready'
  checks: { rag: boolean; llm_config: boolean; database: boolean }
}

const READY_TIMEOUT_MS = 10000

/** Готовность как есть; 503 сохраняет checks в ApiError без изменения /ready. */
export const fetchReadiness = () =>
  apiRequest<IReadiness>(
    '/ready',
    { method: 'GET' },
    'Сервис временно недоступен',
    READY_TIMEOUT_MS
  )

/**
 * Можно ли сейчас запускать анализ через ИИ. Бэкенд готов (`ready`) без
 * настроенной модели только в демо-режиме: в полном режиме без модели
 * `/ready` отвечает 503 (docs/API_CONTRACT.md).
 */
export type AiAvailability = 'available' | 'demo' | 'unknown'

export const aiAvailability = (
  readiness: IReadiness | null
): AiAvailability => {
  if (!readiness || readiness.status !== 'ready') return 'unknown'
  return readiness.checks.llm_config ? 'available' : 'demo'
}

/** Версия API бэкенда из OpenAPI-схемы. */
export const fetchApiVersion = async () =>
  (
    await apiRequest<{ info?: { version?: string } }>(
      '/openapi.json',
      { method: 'GET' },
      'Не удалось получить версию API',
      READY_TIMEOUT_MS
    )
  ).info?.version ?? null

/** Swagger бэкенда по адресу из VITE_BASE_API. */
export const swaggerUrl = () => `${import.meta.env.VITE_BASE_API ?? ''}/docs`

/**
 * Готовность бэкенда. В демо rag и llm_config равны false, но status —
 * ready: для экранов важна только база. Возвращает текст проблемы или null.
 */
export const checkReadiness = async (): Promise<string | null> => {
  try {
    return readinessProblem(await fetchReadiness())
  } catch (error) {
    if (error instanceof ApiError && error.status === 503) {
      return error.readiness ? readinessProblem(error.readiness) : 'Сервис временно недоступен: причина не установлена. Попробуйте позже'
    }
    // 502/504 — прокси перед бэкендом, когда тот выключен или завис.
    if (error instanceof ApiError && [502, 504].includes(error.status)) {
      return 'Сервер Пульса не отвечает. Попробуйте позже'
    }
    return (error as Error).message
  }
}

export const readinessProblem = (result: IReadiness): string | null => {
  if (!result.checks.database) return 'Сервис временно недоступен: база данных не готова. Попробуйте позже'
  if (result.status === 'ready') return null // Offline demo intentionally needs only DB.
  const missing = [!result.checks.rag && 'RAG недоступен', !result.checks.llm_config && 'LLM не настроена'].filter(Boolean)
  return missing.length > 0
    ? `База данных доступна. ${missing.join('; ')}. Возможности анализа ограничены.`
    : 'База данных доступна. Причина неготовности сервиса не установлена.'
}
