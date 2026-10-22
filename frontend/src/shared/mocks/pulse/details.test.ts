import { describe, expect, it } from 'vitest'

import { getInsightDetail } from './details'
import { HISTORY_ROWS } from './summary'
import { FEED_INSIGHT_IDS, PULSE_INSIGHTS } from './insights'

describe('демо-данные инсайтов', () => {
  it('у каждого инсайта ленты и истории есть содержимое страницы', () => {
    const ids = [...FEED_INSIGHT_IDS, ...HISTORY_ROWS.map((r) => r.insightId)]
    for (const id of ids) {
      const detail = getInsightDetail(PULSE_INSIGHTS[id])
      expect(detail.fact, id).not.toBe('')
      expect(detail.log.length, id).toBeGreaterThan(0)
      expect(detail.questions.length, id).toBeGreaterThan(0)
    }
  })

  it('без позиции банка — явное состояние, а не пустой блок', () => {
    expect(getInsightDetail(PULSE_INSIGHTS.eu).bank).toBeNull()
    expect(getInsightDetail(PULSE_INSIGHTS.rate).bank?.change?.current).toBe(
      '14,0% (11.09)'
    )
  })

  it('факты сверены с аналитикой банка: решение ЦБ — 11 сентября', () => {
    const rate = getInsightDetail(PULSE_INSIGHTS.rate)
    expect(rate.fact).toContain('11 сентября')
    expect(rate.bank?.date).toBe('11.09.2026')
  })

  it('сценарии без процентов: только качественные метки', () => {
    for (const id of FEED_INSIGHT_IDS) {
      for (const scenario of getInsightDetail(PULSE_INSIGHTS[id]).scenarios) {
        expect(['Вероятно', 'Возможно', 'Маловероятно']).toContain(
          scenario.likelihood
        )
        expect(scenario.text).not.toMatch(/\d+\s?%\s*вероятн/i)
      }
    }
  })

  it('история ссылается на существующие инсайты', () => {
    for (const row of HISTORY_ROWS) {
      expect(PULSE_INSIGHTS[row.insightId], row.insightId).toBeDefined()
      if (row.updatedInsightId) {
        expect(PULSE_INSIGHTS[row.updatedInsightId]).toBeDefined()
      }
    }
  })
})
