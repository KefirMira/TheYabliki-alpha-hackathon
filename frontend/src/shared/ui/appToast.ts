import { showToast } from '@/hooks/useToast'

/**
 * Единый фасад уведомлений, как в SampoSmart: toast.success / .info / .error.
 * Выводит Toaster из корня приложения — снизу справа, один стиль на весь сайт.
 */
export const toast = {
  success: (message: string) => showToast(message, 'success'),
  info: (message: string) => showToast(message, 'info'),
  error: (message: string) => showToast(message, 'error'),
}
