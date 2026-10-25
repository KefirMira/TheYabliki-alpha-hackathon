import InsightSidePanel from './InsightSidePanel'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mapInsightCard, mapFeedItem } from '@/shared/api/mappers/pulseMappers'
import type { IInsightCard } from '@/store/models/IInsight'
import { SavedPilotNotice } from './SavedPilotNotice'
import { FinancialReviewSection } from './InsightSections'
const artifact = JSON.parse(
  readFileSync(
    path.resolve(process.cwd(), '../backend/fixtures/saved_llm_pilot_v1.json'),
    'utf8'
  )
)
const content = JSON.parse(artifact.content)
const card: IInsightCard = {
  insight_id: 1,
  run_id: 1,
  company_id: 'SYNTH-GATEWAY-MACRO-A',
  type: null,
  relevance: content.relevance,
  summary: content.summary,
  created_at: '2026-10-25T12:00:00Z',
  status: 'COMPLETED',
  news: { id: 1, title: 'Синтетический пример', text: 'Вымышленная новость' },
  risks: content.risks,
  opportunities: content.opportunities,
  recommendations: content.recommendations,
  validation: {
    ...artifact.validation,
    financial_review: artifact.financial_review,
    orchestration: artifact.orchestration,
    saved_pilot_import: {
      ...artifact.metadata,
      version: 'saved-llm-pilot-v1',
      synthetic: true,
      imported_at: '2026-10-25T12:00:00Z',
      artifact_sha256:
        '5c75a2d975712f20303c065adaf64d69337d1812cc6738aa49cc23a2c14a243f',
    },
  },
  sources: artifact.sources.map((s: object) => ({ ...s, synthetic: true })),
  evidence: [],
}
describe('saved synthetic pilot', () => {
  it('keeps the model words and all reviewer findings without claiming truth', () => {
    const { detail } = mapInsightCard(card)
    expect(detail.impact).toBe(content.summary)
    expect(detail.risks).toEqual(content.risks)
    expect(detail.actions).toEqual(content.recommendations)
    expect(detail.bank).toBeNull()
    expect(detail.sources[0].description).toContain('Источник 1')
    render(
      <>
        <SavedPilotNotice detail={detail} />
        <FinancialReviewSection detail={detail} />
        <InsightSidePanel detail={detail} />
      </>
    )
    expect(
      screen.getByRole('heading', { name: 'Синтетический пример' })
    ).toBeInTheDocument()
    expect(
      screen.getByText('Финансовая достоверность не подтверждена')
    ).toBeInTheDocument()
    expect(screen.getByText(/UNKNOWN: 16; NEEDS_REVIEW: 4/)).toBeInTheDocument()
    expect(
      screen.getByText(/включая reasoning: 1452; всего: 2395/)
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Повторного запроса к модели не было/)
    ).toBeInTheDocument()
    expect(screen.getByText(/Сохранённый журнал пилота/)).toBeInTheDocument()
    expect(detail.financialReview?.findings).toHaveLength(20)
    expect(screen.getByText(/Исторический trace пилота от/)).toBeInTheDocument()
  })
  it('labels imported time separately from generation', () => {
    expect(mapFeedItem(card).updated).toContain(
      'Импорт сохранённого результата'
    )
  })
  it('does not manufacture pilot metadata for ordinary or malformed results', () => {
    expect(
      mapInsightCard({ ...card, validation: { passed: true, warnings: [] } })
        .detail.savedPilot
    ).toBeUndefined()
    expect(
      mapInsightCard({
        ...card,
        validation: {
          saved_pilot_import: {
            version: 'saved-llm-pilot-v1',
            synthetic: true,
          },
        },
      }).detail.savedPilot
    ).toBeUndefined()
  })
})
