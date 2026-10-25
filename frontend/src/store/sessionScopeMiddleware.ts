import type { Middleware } from '@reduxjs/toolkit'
import { sessionGeneration } from '@/shared/auth/session'
// Late responses from an earlier login must not repopulate a new actor's store.
export const sessionScopeMiddleware: Middleware = () => {
  const pending = new Map<string, number>()
  return (next) => (action) => {
    const meta = (
      action as { meta?: { requestId?: string; requestStatus?: string } }
    ).meta
    if (meta?.requestId) {
      if (meta.requestStatus === 'pending')
        pending.set(meta.requestId, sessionGeneration())
      else if (pending.has(meta.requestId)) {
        const generation = pending.get(meta.requestId)
        pending.delete(meta.requestId)
        if (generation !== sessionGeneration()) return action
      }
    }
    return next(action)
  }
}
