import { describe, expect, it } from 'vitest'

import type { IInsightCard, IInsightFeedItem } from '@/store/models/IInsight'

import { bankPositionFrom, mapFeedItem, mapInsightCard } from './pulseMappers'

const NOW = Date.parse('2026-01-04T12:00:00Z')

const feedItem = (
  overrides: Partial<IInsightFeedItem> = {}
): IInsightFeedItem => ({
  insight_id: 2,
  run_id: 2,
  company_id: 'DEMO-001',
  type: 'opportunity',
  relevance: 'unknown',
  summary: 'Синтетический инсайт 2',
  created_at: '2026-01-03T12:00:00Z',
  status: 'COMPLETED',
  ...overrides,
})

const card = (overrides: Partial<IInsightCard> = {}): IInsightCard => ({
  ...feedItem(),
  news: { id: 2, title: 'Демо-новость 2', text: 'Текст новости' },
  risks: ['Риск'],
  opportunities: ['Возможность'],
  recommendations: ['Рекомендация'],
  validation: { passed: false, warnings: ['Синтетическая фикстура'] },
  sources: [
    {
      id: 1,
      document: 'synthetic-demo.txt',
      page: 1,
      date: '2026-01',
      synthetic: true,
    },
  ],
  evidence: [
    {
      id: 2,
      evidence_type: 'DOCUMENT',
      text: 'Синтетический фрагмент',
      document: 'synthetic-demo.txt',
      page: 1,
      chunk_id: 1,
      document_date: null,
    },
  ],
  ...overrides,
})

describe('mapFeedItem', () => {
  it('тип API → тип экрана, id строкой, возраст в часах', () => {
    const insight = mapFeedItem(feedItem(), NOW)
    expect(insight).toMatchObject({ id: '2', kind: 'opp', ageHours: 24 })
    expect(insight.updated).toBe('Анализ от 3 января 2026')
  })

  it('unknown-релевантность и отсутствующий тип не выдумываются', () => {
    const insight = mapFeedItem(feedItem({ type: null }), NOW)
    expect(insight.kind).toBe('info')
    expect(insight.relevanceLevel).toBeUndefined()
  })

  it('релевантность словами переносится как есть', () => {
    expect(
      mapFeedItem(feedItem({ relevance: 'high' }), NOW).relevanceLevel
    ).toBe('high')
  })
})

describe('bankPositionFrom', () => {
  it('синтетический документ — позиции банка нет', () => {
    expect(bankPositionFrom(card())).toBeNull()
  })

  it('фрагмент PDF базы знаний — точная цитата как позиция банка', () => {
    const position = bankPositionFrom(
      card({
        sources: [
          {
            id: 1,
            document: 'ALFA-7M26.pdf',
            page: 2,
            chunk_id: 3,
            date: '2026-09',
            provenance: {
              publisher: 'Альфа-Банк',
              attribution_status: 'VERIFIED',
            },
          },
        ],
        evidence: [
          {
            id: 7,
            evidence_type: 'PDF',
            text: 'Точный фрагмент аналитики',
            document: 'ALFA-7M26.pdf',
            page: 2,
            chunk_id: 3,
            document_date: null,
          },
        ],
      })
    )
    expect(position).toEqual({
      author: 'Аналитика Альфа-Банка',
      date: '2026-09',
      quote: 'Точный фрагмент аналитики',
      document: 'ALFA-7M26.pdf · стр. 2',
    })
  })
})

describe('mapInsightCard', () => {
  it('новость — факт, summary — вывод, рекомендации — действия', () => {
    const { insight, detail } = mapInsightCard(card(), NOW)
    expect(insight.title).toBe('Демо-новость 2')
    expect(detail.fact).toBe('Текст новости')
    expect(detail.impact).toBe('Синтетический инсайт 2')
    expect(detail.actions).toEqual(['Рекомендация'])
  })

  it('проверка с замечаниями видна в выводе и в ходе анализа', () => {
    const { detail } = mapInsightCard(card(), NOW)
    expect(detail.confidence).toBe(
      'есть замечания; финансовая достоверность не установлена'
    )
    expect(detail.warnings).toEqual(['Синтетическая фикстура'])
    expect(detail.log.at(-1)).toMatchObject({ warning: true })
  })

  it('пустой validation — не «проверка пройдена», а без итога', () => {
    const { detail } = mapInsightCard(card({ validation: {} }), NOW)
    expect(detail.confidence).toBe('')
    expect(detail.log.some((step) => step.title.includes('Проверка'))).toBe(
      false
    )
  })
})

it('verified PDF with unknown/non-bank publisher is not a bank position', () => {
  for (const publisher of [null, 'Independent publisher']) {
    expect(
      bankPositionFrom(
        card({
          sources: [
            {
              id: 1,
              document: 'ALFA.pdf',
              page: 1,
              chunk_id: 1,
              provenance: {
                format_verified: true,
                publisher,
                attribution_status: 'VERIFIED',
              },
            },
          ],
          evidence: [
            {
              id: 1,
              evidence_type: 'PDF',
              text: 'Exact text',
              document: 'ALFA.pdf',
              page: 1,
              chunk_id: 1,
              document_date: null,
            },
          ],
        })
      )
    ).toBeNull()
  }
})
it('technical JSON success never certifies financial truth', () => {
  const { detail } = mapInsightCard(
    card({ validation: { passed: true, warnings: [] } })
  )
  expect(detail.confidence).toContain('финансовая достоверность не установлена')
  expect(
    detail.log.some((step) =>
      step.title.includes('Проверка достоверности пройдена')
    )
  ).toBe(false)
})

it('preserves financial dispositions instead of treating technical success as truth', () => {
  const findings = [
    ...Array.from({ length: 16 }, () => ({
      code: 'SYNTHETIC',
      disposition: 'UNKNOWN',
      claim: 'Synthetic',
      explanation: 'Needs evidence',
    })),
    ...Array.from({ length: 4 }, () => ({
      code: 'SYNTHETIC',
      disposition: 'NEEDS_REVIEW',
      claim: 'Synthetic',
      explanation: 'Needs expert',
    })),
  ]
  const { detail } = mapInsightCard(
    card({
      validation: {
        passed: true,
        financial_review: { status: 'NEEDS_REVIEW', findings },
      },
    })
  )
  expect(
    detail.financialReview?.findings.filter((f) => f.disposition === 'UNKNOWN')
  ).toHaveLength(16)
  expect(
    detail.financialReview?.findings.filter(
      (f) => f.disposition === 'NEEDS_REVIEW'
    )
  ).toHaveLength(4)
  expect(detail.synthetic).toBe(true)
  expect(detail.confidence).toContain('финансовая достоверность не установлена')
})
