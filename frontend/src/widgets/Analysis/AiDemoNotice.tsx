import { Info } from 'lucide-react'

/**
 * Анализ выключен заранее, а не после 503: по `/ready` видно, что модель
 * не настроена (демо-режим бэкенда).
 */
const AiDemoNotice = () => (
  <div className="flex gap-3 rounded-2xl bg-tone-info px-4 py-3 text-sm leading-5 text-tone-info-fg">
    <Info className="mt-0.5 h-4 w-4 shrink-0" />
    <span>
      Saved-pilot работает офлайн и не отправляет новости в LLM. Для анализа новой
      новости нужно отдельное окружение с настроенным API-ключом, правом анализа
      выбранной компании и разрешением передачи её контекста. Demo-аккаунт доступен
      только для чтения. Готовые инсайты — в ленте.
    </span>
  </div>
)

export default AiDemoNotice
