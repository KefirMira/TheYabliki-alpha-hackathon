/** Тоны тегов: подложка и текст одного цветового семейства (макеты v6). */
export const TAG_TONES = {
  risk: 'bg-tone-risk text-tone-risk-fg',
  opp: 'bg-tone-opp text-tone-opp-fg',
  info: 'bg-tone-info text-tone-info-fg',
  ai: 'bg-tone-ai text-tone-ai-fg',
  bank: 'bg-tone-bank text-tone-bank-fg',
  fact: 'bg-tone-fact text-tone-fact-fg',
  muted: 'bg-line-soft text-ink-3',
} as const

export type TagTone = keyof typeof TAG_TONES
