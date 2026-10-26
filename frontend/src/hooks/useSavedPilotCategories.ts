import { useEffect, useState } from 'react'
import { fetchInsight } from '@/shared/api/insights.api'
import { isSavedPilotCompany } from '@/shared/constants/savedPilot'
import type { IInsightCard } from '@/store/models/IInsight'
import type { IPulseInsight } from '@/store/models/IPulse'

/** View-only excerpts of existing saved results; never new analyses or evidence. */
export const categoryCards = (companyId: string, companyName: string, source: IPulseInsight[], cards: IInsightCard[]): IPulseInsight[] => {
  const parents = new Map(source.map((item) => [item.id, item]))
  return cards.flatMap((card) => {
    const parent = parents.get(String(card.insight_id))
    const imported = card.validation.saved_pilot_import ||
      (card.validation.saved_pilot_collection_import as { mode?: string } | undefined)?.mode === 'REAL_SYNTHETIC'
    if (!parent || card.company_id !== companyId || !imported) return []
    const events = (card.validation.orchestration as { events?: unknown[] } | undefined)?.events
    return (['risk', 'opp'] as const).flatMap((kind) =>
      (kind === 'risk' ? card.risks : card.opportunities).flatMap((text, index) => text.trim() ? [{
        ...parent,
        id: `${companyId}:${parent.id}:${kind}:${index}`,
        parentInsightId: parent.id,
        kind,
        relevanceLevel: undefined,
        title: `${kind === 'risk' ? 'Риск' : 'Возможность'} ${index + 1}: ${card.news.title}`,
        meaning: text,
        companyName,
        evidenceCount: card.evidence.length,
        traceSteps: Array.isArray(events) ? events.length : 0,
      }] : []))
  })
}

/** Only saved demo IDs; server ACL still authorizes every detail request. */
export const useSavedPilotCategories = (companyId: string | null, companyName: string, source: IPulseInsight[]) => {
  const enabled = isSavedPilotCompany(companyId)
  const ids = source.map((item) => item.id).filter((id) => /^\d+$/.test(id)).join(',')
  const key = `${companyId ?? ''}|${ids}`
  const [state, setState] = useState<{ key: string; cards: IInsightCard[]; error: string }>({ key: '', cards: [], error: '' })
  useEffect(() => {
    if (!enabled || !companyId || !ids) return
    let stale = false
    Promise.all(ids.split(',').map((id) => fetchInsight(companyId, Number(id))))
      .then((cards) => { if (!stale) setState({ key, cards, error: '' }) })
      .catch(() => { if (!stale) setState({ key, cards: [], error: 'Не удалось загрузить категории сохранённых анализов. Исходные инсайты доступны; обновите страницу для повторной проверки.' }) })
    return () => { stale = true }
  }, [companyId, enabled, ids, key])
  const current = enabled && companyId && state.key === key
  return {
    items: current ? [...source, ...categoryCards(companyId, companyName, source, state.cards)] : source,
    loading: enabled && Boolean(ids) && !current,
    error: current ? state.error : '',
  }
}
