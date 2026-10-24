/** Приём новости: `POST /api/news` (docs/NEWS_INGESTION_API.md). */
export interface IExternalNewsInput {
  title: string
  content: string
  url?: string
  source_name?: string
  source_id?: string
  /** ISO 8601 с явным часовым поясом. */
  published_at?: string
  language?: string
}

/** Расхождения с уже сохранённой новостью при дубликате. */
export type NewsDiagnostic =
  | 'URL_MISMATCH'
  | 'SOURCE_IDENTITY_MISMATCH'
  | 'CONTENT_MISMATCH'
  | 'TITLE_MISMATCH'
  | 'METADATA_MISMATCH'

/** Ответ приёма: 201 — новая, 200 — уже сохранённая, без перезаписи. */
export interface IIngestedNews {
  news_id: number
  created: boolean
  duplicate: boolean
  diagnostics: NewsDiagnostic[]
  news: {
    title: string
    url: string | null
    source_name: string | null
    source_id: string | null
    published_at: string | null
    language: string | null
    input_kind: string
  }
}
