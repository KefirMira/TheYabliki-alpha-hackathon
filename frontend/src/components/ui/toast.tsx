import * as React from 'react'
import * as ToastPrimitives from '@radix-ui/react-toast'
import { X } from 'lucide-react'

import { cn } from '@/lib/utils'

/**
 * Тост на Radix, анимация как в shadcn-тостах SampoSmart: выезжает снизу,
 * закрывается затуханием с уходом вправо, смахивается свайпом вправо.
 * Внешний вид — тёмный тост макета.
 */
const ToastProvider = ToastPrimitives.Provider

const ToastViewport = React.forwardRef<
  React.ElementRef<typeof ToastPrimitives.Viewport>,
  React.ComponentPropsWithoutRef<typeof ToastPrimitives.Viewport>
>(({ className, ...props }, ref) => (
  <ToastPrimitives.Viewport
    ref={ref}
    className={cn(
      'fixed bottom-0 right-0 z-[100] flex max-h-screen w-full flex-col p-4 outline-none md:max-w-[452px] md:p-6',
      className
    )}
    {...props}
  />
))
ToastViewport.displayName = ToastPrimitives.Viewport.displayName

const Toast = React.forwardRef<
  React.ElementRef<typeof ToastPrimitives.Root>,
  React.ComponentPropsWithoutRef<typeof ToastPrimitives.Root>
>(({ className, ...props }, ref) => (
  <ToastPrimitives.Root
    ref={ref}
    className={cn(
      'group pointer-events-auto relative flex w-full items-center gap-2.5 overflow-hidden rounded-[14px] bg-ink py-3 pl-4 pr-10 text-sm font-medium text-white shadow-[0_16px_48px_rgba(18,19,22,0.24)] transition-all',
      // Свайп: тост едет за пальцем, при отмене возвращается на место.
      'data-[swipe=cancel]:translate-x-0 data-[swipe=end]:translate-x-[var(--radix-toast-swipe-end-x)] data-[swipe=move]:translate-x-[var(--radix-toast-swipe-move-x)] data-[swipe=move]:transition-none',
      // Появление снизу, закрытие — затухание с уходом вправо.
      'data-[state=open]:animate-in data-[state=open]:slide-in-from-bottom-full data-[state=closed]:animate-out data-[state=closed]:fade-out-80 data-[state=closed]:slide-out-to-right-full data-[swipe=end]:animate-out',
      className
    )}
    {...props}
  />
))
Toast.displayName = ToastPrimitives.Root.displayName

const ToastDescription = React.forwardRef<
  React.ElementRef<typeof ToastPrimitives.Description>,
  React.ComponentPropsWithoutRef<typeof ToastPrimitives.Description>
>(({ className, ...props }, ref) => (
  <ToastPrimitives.Description
    ref={ref}
    className={cn('min-w-0 [overflow-wrap:anywhere]', className)}
    {...props}
  />
))
ToastDescription.displayName = ToastPrimitives.Description.displayName

/** Крестик появляется при наведении на тост или фокусе с клавиатуры. */
const ToastClose = React.forwardRef<
  React.ElementRef<typeof ToastPrimitives.Close>,
  React.ComponentPropsWithoutRef<typeof ToastPrimitives.Close>
>(({ className, ...props }, ref) => (
  <ToastPrimitives.Close
    ref={ref}
    aria-label="Закрыть"
    className={cn(
      'absolute right-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-lg text-white/50 opacity-0 transition-opacity hover:text-white focus:opacity-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/40 group-hover:opacity-100',
      className
    )}
    {...props}
  >
    <X className="h-4 w-4" />
  </ToastPrimitives.Close>
))
ToastClose.displayName = ToastPrimitives.Close.displayName

export { Toast, ToastClose, ToastDescription, ToastProvider, ToastViewport }
