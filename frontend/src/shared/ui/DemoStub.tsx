import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'
import { toast } from '@/shared/ui/appToast'

interface DemoStubProps {
  /** Название для подсказки: «Платежи», «Создать платёж»… */
  label: string
  className?: string
  children: ReactNode
}

/**
 * Нерабочий элемент оболочки банка: приглушён, без hover, курсор «нельзя»,
 * по клику — подсказка, что в прототипе работает только Пульс. Клик в
 * пустоту выглядел бы как ошибка, подсказка — как задуманное поведение.
 */
const DemoStub = ({ label, className, children }: DemoStubProps) => (
  <span
    role="button"
    aria-disabled="true"
    aria-label={`${label} — в прототипе не работает`}
    onClick={() =>
      toast.info(
        `«${label}» — эта часть интернет-банка в прототипе не работает. Откройте «Пульс бизнеса»`
      )
    }
    className={cn('cursor-not-allowed select-none opacity-50', className)}
  >
    {children}
  </span>
)

export default DemoStub
