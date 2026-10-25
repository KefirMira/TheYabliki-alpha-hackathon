import { describe, expect, it } from 'vitest'

import {
  type NewsFormValues,
  newsFormError,
  newsPayload,
  MANUAL_SOURCE_NAME,
  SYNTHETIC_SOURCE_NAME,
} from './news.api'
import { aiAvailability } from './system.api'

const form = (patch: Partial<NewsFormValues> = {}): NewsFormValues => ({
  title: ' Заголовок ',
  content: ' Текст ',
  url: '',
  publishedAt: '',
  synthetic: false,
  ...patch,
})

describe('newsFormError', () => {
  it('требует заголовок и текст', () => {
    expect(newsFormError(form({ title: ' ' }))).toBe(
      'Заполните заголовок и текст новости'
    )
  })

  it('синтетической новости нельзя ссылку на реальный сайт', () => {
    expect(
      newsFormError(form({ synthetic: true, url: 'https://rbc.ru/news/1' }))
    ).toMatch(/example\.invalid/)
    expect(
      newsFormError(
        form({ synthetic: true, url: 'https://news.example.invalid/a' })
      )
    ).toBeNull()
  })

  it('ссылка только http/https', () => {
    expect(newsFormError(form({ url: 'rbc.ru' }))).toMatch(/http/)
  })
})

describe('newsPayload', () => {
  it('обычная новость — без маркировки, с языком и обрезанными полями', () => {
    expect(newsPayload(form({ url: ' https://rbc.ru/a ' }))).toEqual({
      title: 'Заголовок',
      content: 'Текст',
      language: 'ru',
      url: 'https://rbc.ru/a',
    })
  })

  it('синтетическая — маркировка демо и идентификатор из текста', () => {
    const payload = newsPayload(form({ synthetic: true }))
    const same = newsPayload(
      form({ synthetic: true, url: 'https://x.invalid' })
    )
    const other = newsPayload(form({ synthetic: true, content: 'Другой' }))

    expect(payload.source_name).toBe(SYNTHETIC_SOURCE_NAME)
    expect(payload.source_id).toMatch(/^SYNTH-UI-[0-9a-f]{8}$/)
    // Та же новость — тот же идентификатор, другая — другой.
    expect(same.source_id).toBe(payload.source_id)
    expect(other.source_id).not.toBe(payload.source_id)
  })

  it('обычная без ссылки — свой источник и устойчивый ID, без дублей', () => {
    const payload = newsPayload(form())
    const again = newsPayload(form({ publishedAt: '2026-10-24T15:30' }))
    const other = newsPayload(form({ content: 'Другой текст' }))

    expect(payload.source_name).toBe(MANUAL_SOURCE_NAME)
    expect(payload.source_id).toMatch(/^UI-[0-9a-f]{16}$/)
    // Повтор той же новости (хоть после «Очистить») — тот же ID.
    expect(again.source_id).toBe(payload.source_id)
    expect(other.source_id).not.toBe(payload.source_id)
  })

  it('обычная со ссылкой — только ссылка, без своей пары', () => {
    const payload = newsPayload(form({ url: 'https://rbc.ru/a' }))

    expect(payload.source_name).toBeUndefined()
    expect(payload.source_id).toBeUndefined()
  })

  it('время публикации — ISO с поясом', () => {
    const payload = newsPayload(form({ publishedAt: '2026-10-24T15:30' }))

    expect(payload.published_at).toMatch(/Z$/)
  })
})

describe('aiAvailability', () => {
  it('готовый сервис без модели — демо-режим', () => {
    expect(
      aiAvailability({
        status: 'ready',
        checks: { rag: false, llm_config: false, database: true },
      })
    ).toBe('demo')
  })

  it('модель настроена — ИИ доступен; нет ответа — неизвестно', () => {
    expect(
      aiAvailability({
        status: 'ready',
        checks: { rag: true, llm_config: true, database: true },
      })
    ).toBe('available')
    expect(aiAvailability(null)).toBe('unknown')
  })
})
