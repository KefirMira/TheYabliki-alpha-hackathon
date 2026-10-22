import { CircleCheck } from 'lucide-react'

/**
 * Всплывающее подтверждение после сохранения (снизу справа), видно при любой
 * прокрутке. Без текста ничего не рисует.
 */
const FlashMessage = ({ message }: { message: string | null }) =>
  message ? (
    <p
      role="status"
      className="fixed bottom-6 right-6 z-50 flex max-w-[420px] items-center gap-2.5 rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-white shadow-[0_16px_48px_rgba(18,19,22,0.24)] animate-in fade-in-0 slide-in-from-bottom-2"
    >
      <CircleCheck className="h-4 w-4 shrink-0 text-[#6BD49A]" />
      {message}
    </p>
  ) : null

export default FlashMessage
