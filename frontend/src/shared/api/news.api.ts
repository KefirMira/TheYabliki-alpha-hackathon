import type { ICreatedAnalysis } from '@/store/models/IInsight'
import type {
  IExternalNewsInput,
  IIngestedNews,
  NewsDiagnostic,
} from '@/store/models/INews'

import { apiRequest } from './request'

/** Анализ через LLM идёт дольше обычного запроса. */
const ANALYSIS_TIMEOUT_MS = 120000

/** В демо бэкенд принимает только такую маркировку (docs/NEWS_INGESTION_API.md). */
export const SYNTHETIC_SOURCE_NAME = 'synthetic-demo'
const SYNTHETIC_ID_PREFIX = 'SYNTH-UI-'

/**
 * Источник обычной новости, добавленной вручную в интерфейсе. Без ссылки
 * и без пары source_name/source_id бэкенд считает каждый запрос новой
 * новостью — пара нужна, чтобы повтор той же новости не задвоил её.
 */
export const MANUAL_SOURCE_NAME = 'pulse-ui'
const MANUAL_ID_PREFIX = 'UI-'

/** Сохранить новость без ИИ. Повтор той же новости вернёт её, не создав копию. */
export const ingestNews = (news: IExternalNewsInput) =>
  apiRequest<IIngestedNews>(
    '/api/news',
    { method: 'POST', body: JSON.stringify(news) },
    'Не удалось сохранить новость'
  )

/**
 * Анализ сохранённой новости для компании. Повтор по уже готовой паре
 * возвращает сохранённый результат без ИИ, по идущей — 409. Автоматически
 * не повторяем: новый запуск — новый вызов LLM.
 */
export const analyzeSavedNews = (companyId: string, newsId: number) =>
  apiRequest<ICreatedAnalysis>(
    `/api/companies/${encodeURIComponent(companyId)}/news/${newsId}/analyses`,
    { method: 'POST' },
    'Не удалось проанализировать новость',
    ANALYSIS_TIMEOUT_MS
  )

export interface NewsFormValues {
  title: string
  content: string
  url: string
  /** Значение datetime-local: «2026-10-24T15:30», без пояса. */
  publishedAt: string
  synthetic: boolean
}

/** Синтетическая новость может ссылаться только на example.invalid. */
const syntheticUrlAllowed = (url: string) => {
  try {
    const host = new URL(url).hostname
    return host === 'example.invalid' || host.endsWith('.example.invalid')
  } catch {
    return false
  }
}

/** Ошибка формы или null — до отправки, чтобы не ловить 422/403. */
export const newsFormError = (form: NewsFormValues): string | null => {
  if (!form.title.trim() || !form.content.trim()) {
    return 'Заполните заголовок и текст новости'
  }
  const url = form.url.trim()
  if (url && !/^https?:\/\//i.test(url)) {
    return 'Ссылка должна начинаться с http:// или https://'
  }
  if (url && form.synthetic && !syntheticUrlAllowed(url)) {
    return 'У синтетической новости ссылка может быть только на example.invalid — или оставьте поле пустым'
  }
  return null
}

/** Короткий устойчивый хеш строки (FNV-1a, 32 бита) — для идентификатора. */
const fnv1a = (value: string) => {
  let hash = 0x811c9dc5
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 0x01000193)
  }
  return (hash >>> 0).toString(16).padStart(8, '0')
}

/**
 * Тело запроса из формы. Время публикации переводим в ISO с поясом:
 * бэкенд не принимает время без него.
 *
 * Повтор той же новости бэкенд узнаёт по ссылке или по паре
 * source_name/source_id (docs/NEWS_INGESTION_API.md). Поэтому:
 * - синтетической — маркировка демо-набора и идентификатор из текста;
 * - обычной без ссылки — свой источник и идентификатор из текста;
 * - обычной со ссылкой — только ссылка: своя пара к новости, которую уже
 *   загрузил парсер под другим источником, дала бы 409 NEWS_IDENTITY_CONFLICT.
 */
export const newsPayload = (form: NewsFormValues): IExternalNewsInput => {
  const payload: IExternalNewsInput = {
    title: form.title.trim(),
    content: form.content.trim(),
    language: 'ru',
  }
  const url = form.url.trim()
  if (url) payload.url = url
  if (form.publishedAt) {
    payload.published_at = new Date(form.publishedAt).toISOString()
  }
  const text = `${payload.title}\n${payload.content}`
  if (form.synthetic) {
    payload.source_name = SYNTHETIC_SOURCE_NAME
    payload.source_id = `${SYNTHETIC_ID_PREFIX}${fnv1a(text)}`
  } else if (!url) {
    payload.source_name = MANUAL_SOURCE_NAME
    // 64 бита из двух хешей: у разных новостей ID практически не совпадёт,
    // а одна и та же новость всегда даёт один и тот же.
    payload.source_id = `${MANUAL_ID_PREFIX}${fnv1a(text)}${fnv1a(`pulse:${text}`)}`
  }
  return payload
}

/**
 * Отпечаток новости из формы — то, что уйдёт в POST /api/news. Совпал с
 * прошлой отправкой — новость уже в базе, сохранять её снова не нужно.
 */
export const newsKeyOf = (form: NewsFormValues) =>
  JSON.stringify(newsPayload(form))

export const NEWS_DIAGNOSTIC_LABEL: Record<NewsDiagnostic, string> = {
  URL_MISMATCH: 'ссылка отличается от сохранённой',
  SOURCE_IDENTITY_MISMATCH: 'источник отличается от сохранённого',
  CONTENT_MISMATCH: 'текст отличается от сохранённого',
  TITLE_MISMATCH: 'заголовок отличается от сохранённого',
  METADATA_MISMATCH: 'дата или язык отличаются от сохранённых',
}
