import { Info } from 'lucide-react'

/**
 * Анализ выключен заранее, а не после 503: по `/ready` видно, что модель
 * не настроена (демо-режим бэкенда).
 */
const AiDemoNotice = () => (
  <div className="flex gap-3 rounded-2xl bg-tone-info px-4 py-3 text-sm leading-5 text-tone-info-fg">
    <Info className="mt-0.5 h-4 w-4 shrink-0" />
    <span>
      Сервис работает в демо-режиме: модель не подключена, поэтому анализ
      новостей сейчас недоступен. Готовые инсайты — в ленте.
    </span>
  </div>
)

export default AiDemoNotice
