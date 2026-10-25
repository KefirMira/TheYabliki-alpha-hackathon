/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Базовый адрес API бэкенда «Пульса бизнеса». */
  readonly VITE_BASE_API: string
  /** source_id компаний для переключателя, через запятую (до авторизации). */
  readonly VITE_DEMO_COMPANY_IDS?: string
  /** Тестовые учётки: «логин=ID,ID;логин2=ID» (до авторизации в API). */
  readonly VITE_DEMO_ACCOUNTS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
