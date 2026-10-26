import { readFileSync } from 'node:fs'
import path from 'node:path'
import { act, render, renderHook, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { categoryCards, useSavedPilotCategories } from './useSavedPilotCategories'
import { fetchInsight } from '@/shared/api/insights.api'
import type { IInsightCard } from '@/store/models/IInsight'
import { mapFeedItem } from '@/shared/api/mappers/pulseMappers'
import { filterFeed } from '@/widgets/Insights/feedFilter'
import InsightCard from '@/widgets/Insights/InsightCard'
vi.mock('@/shared/api/insights.api', () => ({ fetchInsight: vi.fn() }))
const collection = JSON.parse(readFileSync(path.resolve(process.cwd(), '../backend/fixtures/saved_pilot_collection_v1.json'), 'utf8'))
const inputs = JSON.parse(readFileSync(path.resolve(process.cwd(), '../backend/fixtures/pilot_collection_inputs_v1.json'), 'utf8'))
const legacy = JSON.parse(readFileSync(path.resolve(process.cwd(), '../backend/fixtures/saved_llm_pilot_v1.json'), 'utf8'))
const cards: IInsightCard[] = collection.records.map((r, i) => ({
  ...r.normalized, insight_id: i + 2, run_id: i + 2,
  company_id: inputs.scenarios.find((s) => s.scenario_id === r.scenario_id).company_id,
  type: null, created_at: r.generated_at, status: 'COMPLETED',
  news: { id: i + 2, title: inputs.scenarios.find((s) => s.scenario_id === r.scenario_id).title, text: 'Synthetic' },
  validation: { saved_pilot_collection_import: { mode: r.mode }, orchestration: r.orchestration },
  sources: [], evidence: [{ id: 1, evidence_type: 'DOCUMENT', text: 'source', document: null, page: null, chunk_id: null, document_date: null }],
}))
cards.push({ ...JSON.parse(legacy.content), insight_id: 1, run_id: 1, company_id: 'SYNTH-GATEWAY-MACRO-A', type: null,
  created_at: '2026-10-25T12:00:00Z', status: 'COMPLETED', news: { id: 1, title: 'Историческая ставка', text: 'Synthetic' },
  validation: { saved_pilot_import: legacy.metadata, orchestration: legacy.orchestration }, sources: [], evidence: [] })
const sourceOf = (list: IInsightCard[]) => list.map((card) => mapFeedItem(card))
beforeEach(() => vi.clearAllMocks())

describe('view-only categories from nine saved responses', () => {
  it.each(inputs.companies)('keeps exact points and filters for $source_id', (company) => {
    const own = cards.filter((card) => card.company_id === company.source_id)
    expect(own).toHaveLength(3)
    const before = JSON.stringify(own)
    const source = sourceOf(own)
    const derived = categoryCards(company.source_id, company.display_name, source, own)
    const risks = own.flatMap((card) => card.risks)
    const opps = own.flatMap((card) => card.opportunities)
    expect(derived.filter((item) => item.kind === 'risk').map((item) => item.meaning)).toEqual(risks)
    expect(derived.filter((item) => item.kind === 'opp').map((item) => item.meaning)).toEqual(opps)
    expect(new Set(derived.map((item) => item.id)).size).toBe(derived.length)
    expect(derived.every((item) => item.parentInsightId && item.relevanceLevel === undefined)).toBe(true)
    const all = [...source, ...derived]
    expect(filterFeed(all, { type: 'risk', sort: 'time', favoritesOnly: false }, []).items).toHaveLength(risks.length)
    expect(filterFeed(all, { type: 'opp', sort: 'time', favoritesOnly: false }, []).items).toHaveLength(opps.length)
    expect(filterFeed(all, { type: 'all', sort: 'time', favoritesOnly: false }, []).counts.all).toBe(3 + risks.length + opps.length)
    expect(JSON.stringify(own)).toBe(before)
  })
  it('links a category to the original ACL-protected detail, never its virtual ID', () => {
    const card = cards[0]; const item = categoryCards(card.company_id, 'Учебная металлургия', sourceOf([card]), [card])[0]
    render(<MemoryRouter><InsightCard insight={item} /></MemoryRouter>)
    expect(screen.getByRole('link')).toHaveAttribute('href', '/pulse/insights/' + card.insight_id)
    expect(screen.getByText(/Компания: Учебная металлургия/)).toBeInTheDocument()
    expect(screen.getByText(/Финансовая достоверность не подтверждена/)).toBeInTheDocument()
    expect(screen.getByText(/источники и журнал/)).toBeInTheDocument()
  })
  it('rejects mismatched companies and unmarked ordinary records', () => {
    expect(categoryCards('FOREIGN', 'Other', sourceOf(cards), cards)).toEqual([])
    const card = { ...cards[0], validation: {} }
    expect(categoryCards(card.company_id, 'Own', sourceOf([card]), [card])).toEqual([])
  })
  it('does not fetch category details outside the saved demo', () => {
    renderHook(() => useSavedPilotCategories('ORDINARY', 'Other', sourceOf([cards[0]])))
    expect(fetchInsight).not.toHaveBeenCalled()
  })
  it('discards old company results after switching', async () => {
    const metal = cards.find((c) => c.company_id === 'SYNTH-COLLECTION-METAL')!
    const retail = cards.find((c) => c.company_id === 'SYNTH-COLLECTION-RETAIL')!
    let resolveOld!: (card: IInsightCard) => void
    vi.mocked(fetchInsight).mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve }))
      .mockResolvedValueOnce(retail)
    const { result, rerender } = renderHook(({ card }) => useSavedPilotCategories(card.company_id, card.company_id, sourceOf([card])), { initialProps: { card: metal } })
    rerender({ card: retail })
    await waitFor(() => expect(result.current.loading).toBe(false))
    await act(async () => resolveOld(metal))
    expect(result.current.items.filter((item) => item.parentInsightId).every((item) => item.companyName === retail.company_id)).toBe(true)
    expect(fetchInsight).toHaveBeenCalledTimes(2)
  })
  it('shows a safe error with originals preserved and no automatic retry', async () => {
    vi.mocked(fetchInsight).mockRejectedValueOnce(new Error('private transport detail'))
    const card=cards[0]
    const { result }=renderHook(() => useSavedPilotCategories(card.company_id, 'Own', sourceOf([card])))
    await waitFor(() => expect(result.current.error).not.toBe(''))
    expect(result.current.error).not.toContain('private')
    expect(result.current.items).toHaveLength(1)
    expect(fetchInsight).toHaveBeenCalledTimes(1)
  })
})
