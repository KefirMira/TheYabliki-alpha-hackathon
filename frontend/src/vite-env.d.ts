/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Базовый адрес API бэкенда «Пульса бизнеса». */
  readonly VITE_BASE_API: string
  /** source_id компаний для переключателя, через запятую (до авторизации). */
  readonly VITE_DEMO_COMPANY_IDS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
