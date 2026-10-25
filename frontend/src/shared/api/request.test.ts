import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  REQUEST_TIMEOUT_MESSAGE,
  SERVER_UNREACHABLE_MESSAGE,
} from './apiErrors'
import { ApiError, apiRequest } from './request'

const jsonResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

// Промис запроса, который должен упасть: возвращает ApiError для проверок.
const failure = (promise: Promise<unknown>): Promise<ApiError> =>
  promise.then(
    () => {
      throw new Error('Ожидалась ошибка запроса')
    },
    (error: ApiError) => error
  )

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('apiRequest', () => {
  it('возвращает тело успешного ответа', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(200, { ok: true }))
    )

    await expect(
      apiRequest('/x', { method: 'GET' }, 'Ошибка')
    ).resolves.toEqual({ ok: true })
  })

  it('код бэкенда превращается в русский текст', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(404, {
          detail: { code: 'COMPANY_NOT_FOUND', message: 'not found' },
        })
      )
    )

    const error = await failure(apiRequest('/x', { method: 'GET' }, 'Ошибка'))
    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('COMPANY_NOT_FOUND')
    expect(error.status).toBe(404)
    expect(error.message).toBe('Компания не найдена')
  })

  it('422 FastAPI без кода — фолбэк вызывающей стороны', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse(422, { detail: [{ msg: 'field required' }] })
        )
    )

    const error = await failure(
      apiRequest('/x', { method: 'GET' }, 'Свой текст')
    )
    expect(error.code).toBeNull()
    expect(error.message).toBe('Свой текст')
  })

  it('сетевая ошибка — понятный текст и код NETWORK', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    )

    const error = await failure(apiRequest('/x', { method: 'GET' }, 'Ошибка'))
    expect(error.code).toBe('NETWORK')
    expect(error.message).toBe(SERVER_UNREACHABLE_MESSAGE)
  })

  it('тело ошибки не JSON — фолбэк вызывающей стороны', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('Bad Gateway', { status: 502 }))
    )

    const error = await failure(
      apiRequest('/x', { method: 'GET' }, 'Свой текст')
    )
    expect(error.status).toBe(502)
    expect(error.code).toBeNull()
    expect(error.message).toBe('Свой текст')
  })

  it('таймаут при чтении тела ошибки — код TIMEOUT', async () => {
    vi.useFakeTimers()
    // Сервер прислал статус ошибки, но тело так и не пришло: чтение
    // прерывается только сигналом таймаута.
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((_url: string, init: RequestInit) =>
        Promise.resolve({
          ok: false,
          status: 500,
          json: () =>
            new Promise((_resolve, reject) => {
              init.signal?.addEventListener('abort', () =>
                reject(new DOMException('Aborted', 'AbortError'))
              )
            }),
        })
      )
    )

    const pending = failure(apiRequest('/x', { method: 'GET' }, 'Ошибка'))
    await vi.advanceTimersByTimeAsync(20000)
    const error = await pending

    expect(error.code).toBe('TIMEOUT')
    expect(error.message).toBe(REQUEST_TIMEOUT_MESSAGE)
  })
})
