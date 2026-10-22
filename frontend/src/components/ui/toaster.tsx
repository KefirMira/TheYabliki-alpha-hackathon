import { CircleAlert, CircleCheck, type LucideIcon } from 'lucide-react'

import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastViewport,
} from '@/components/ui/toast'
import {
  dismissToast,
  type ToastVariant,
  useToastState,
} from '@/hooks/useToast'
import { cn } from '@/lib/utils'
import { TOAST_DURATION } from '@/shared/constants/toast'

// У подсказки (info) значка нет — только текст.
const ICONS: Partial<
  Record<ToastVariant, { icon: LucideIcon; className: string }>
> = {
  success: { icon: CircleCheck, className: 'text-[#6BD49A]' },
  error: { icon: CircleAlert, className: 'text-[#FF8A80]' },
}

/**
 * Место вывода тостов — один раз в корне приложения. Radix отвечает за
 * таймер показа (с паузой при наведении), анимацию, свайп и доступность;
 * стор (useToast) — за список тостов.
 */
export const Toaster = () => {
  const { toasts } = useToastState()

  return (
    <ToastProvider duration={TOAST_DURATION} swipeDirection="right">
      {toasts.map(({ id, message, variant, open }) => {
        const icon = ICONS[variant]
        return (
          <Toast
            key={id}
            open={open}
            // Закрытие по таймеру, свайпу, крестику и Esc.
            onOpenChange={(next) => !next && dismissToast(id)}
          >
            {icon && (
              <icon.icon className={cn('h-4 w-4 shrink-0', icon.className)} />
            )}
            <ToastDescription>{message}</ToastDescription>
            <ToastClose />
          </Toast>
        )
      })}
      <ToastViewport />
    </ToastProvider>
  )
}
