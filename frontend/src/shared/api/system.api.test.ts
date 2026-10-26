import { afterEach, describe, expect, it, vi } from 'vitest'

import { SERVER_UNREACHABLE_MESSAGE } from './apiErrors'
import { checkReadiness, readinessProblem } from './system.api'

const DB_PROBLEM =
  'Сервис временно недоступен: база данных не готова. Попробуйте позже'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('readinessProblem', () => {
  it('демо без RAG и LLM считается готовым', () => {
    expect(
      readinessProblem({
        status: 'ready',
        checks: { rag: false, llm_config: false, database: true },
      })
    ).toBeNull()
  })

  it('без базы — проблема', () => {
    expect(
      readinessProblem({
        status: 'not_ready',
        checks: { rag: true, llm_config: true, database: false },
      })
    ).toBe(DB_PROBLEM)
  })
})

describe('checkReadiness', () => {
  it('503 от /ready — база не готова', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            status: 'not_ready',
            checks: { rag: false, llm_config: false, database: false },
          }),
          { status: 503, headers: { 'Content-Type': 'application/json' } }
        )
      )
    )
    await expect(checkReadiness()).resolves.toBe(DB_PROBLEM)
  })

  it('502 от прокси — сервер Пульса не отвечает', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('Bad Gateway', { status: 502 }))
    )
    await expect(checkReadiness()).resolves.toBe(
      'Сервер Пульса не отвечает. Попробуйте позже'
    )
  })

  it('сервер не отвечает — сообщение о недоступности', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('fail')))
    await expect(checkReadiness()).resolves.toBe(SERVER_UNREACHABLE_MESSAGE)
  })
})


describe('accurate partial readiness banner', () => {
  it('HTTP503 with DB ready and RAG absent never reports DB failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({status:'not_ready',checks:{database:true,rag:false,llm_config:true}}),{status:503})))
    const message=await checkReadiness()
    expect(message).toContain('База данных доступна')
    expect(message).toContain('RAG недоступен')
    expect(message).not.toContain('база данных не готова')
  })
  it('LLM config failure is distinct from DB failure', () => {
    expect(readinessProblem({status:'not_ready',checks:{database:true,rag:true,llm_config:false}})).toContain('LLM не настроена')
  })
  it('unknown503 does not invent a database outage or display arbitrary body', async () => {
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({private_error:'must not display'}),{status:503})))
    expect(await checkReadiness()).toBe('Сервис временно недоступен: причина не установлена. Попробуйте позже')
  })
})
