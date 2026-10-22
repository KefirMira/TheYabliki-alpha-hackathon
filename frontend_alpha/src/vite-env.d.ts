/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Базовый адрес API бэкенда «Пульса бизнеса». */
  readonly VITE_BASE_API: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
