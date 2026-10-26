import InsightSidePanel from './InsightSidePanel'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mapInsightCard, mapFeedItem } from '@/shared/api/mappers/pulseMappers'
import type { IInsightCard } from '@/store/models/IInsight'
import { SavedPilotNotice } from './SavedPilotNotice'
import { FinancialReviewSection, Sources } from './InsightSections'
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
    expect(screen.getByText(/Сохранённый настоящий ответ/)).toBeInTheDocument()
    expect(screen.getByText(/Источники — учебные TXT, не аналитика Альфа-Банка/)).toBeInTheDocument()
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


describe('prepared collection labels', () => {
  const collectionCard = (mode: string, url = 'https://www.cbr.ru/press/') => ({
    ...card, company_id: 'SYNTH-COLLECTION-METAL',
    validation: { passed: false, warnings: ['SYNTHETIC_COMPANY_HYPOTHETICAL_NEWS'],
      financial_review: artifact.financial_review,
      saved_pilot_collection_import: { mode, model: mode === 'FAKE_TEST_ONLY' ? 'fake-sdk' : 'deepseek/deepseek-v4.1-flash',
        generated_at: '2026-10-25T10:00:00Z', imported_at: '2026-10-26T10:00:00Z', scenario_id: 'metal-rate' } },
    sources: [{ id: 1, document: 'public-cbr.txt', page: 1, chunk_id: 1, origin_url: url,
      origin_publisher: 'Банк России', page_is_exported_excerpt: true,
      provenance: { publisher: null, attribution_status: 'UNKNOWN' } }],
  })
  it('never labels fake SDK content as a real model answer', () => {
    const { detail } = mapInsightCard(collectionCard('FAKE_TEST_ONLY'))
    render(<SavedPilotNotice detail={detail} />)
    expect(screen.getByText(/Технический fake SDK тест/)).toBeInTheDocument()
    expect(screen.queryByText(/Сохранённый настоящий ответ/)).not.toBeInTheDocument()
    expect(detail.bank).toBeNull()
  })
  it('keeps generation/import dates separate and renders public source links', () => {
    const { detail } = mapInsightCard(collectionCard('REAL_SYNTHETIC'))
    render(<><SavedPilotNotice detail={detail} /><Sources detail={detail} /></>)
    expect(screen.getByText(/Сохранённый настоящий ответ deepseek/)).toBeInTheDocument()
    expect(screen.getByText(/Генерация: 2026-10-25.*Импорт: 2026-10-26/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'public-cbr.txt' })).toHaveAttribute('href', 'https://www.cbr.ru/press/')
    expect(detail.sources[0].description).toContain('не страница PDF')
    expect(detail.bank).toBeNull()
    expect(mapFeedItem(collectionCard('REAL_SYNTHETIC')).updated).toContain('Импорт сохранённого результата')
  })
  it('rejects unsafe links and unknown collection mode', () => {
    const { detail } = mapInsightCard(collectionCard('unknown', 'javascript:alert(1)'))
    expect(detail.collectionPilot).toBeUndefined()
    expect(detail.sources[0].url).toBeUndefined()
  })
})


describe('approved eight real collection records', () => {
  const release = JSON.parse(readFileSync(path.resolve(process.cwd(), '../backend/fixtures/saved_pilot_collection_v1.json'), 'utf8'))
  it.each(release.records)('preserves real words, reviewer and trace for $scenario_id', (record) => {
    const { detail } = mapInsightCard({ ...card, ...record.normalized,
      summary: record.normalized.summary, sources: [],
      validation: { passed: false, financial_review: record.financial_review,
        orchestration: record.orchestration,
        saved_pilot_collection_import: { scenario_id: record.scenario_id, mode: record.mode,
          model: record.model, generated_at: record.generated_at, imported_at: '2026-10-26',
          content_sha256: record.content_sha256, expert_review: record.expert_review } } })
    expect(detail.impact).toBe(record.normalized.summary)
    expect(detail.financialReview?.findings).toHaveLength(record.financial_review.findings.length)
    expect(detail.collectionPilot?.events).toHaveLength(6)
    render(<><SavedPilotNotice detail={detail} /><FinancialReviewSection detail={detail} /></>)
    expect(screen.getByText(/Сохранённый журнал анализа/)).toBeInTheDocument()
    expect(screen.getByText(/Компании и новости синтетические/)).toBeInTheDocument()
    expect(screen.getByText('Финансовая достоверность не подтверждена', { exact: true })).toBeInTheDocument()
    expect(screen.getByText(/Оговорки экспертного просмотра/)).toBeInTheDocument()
  })
})
