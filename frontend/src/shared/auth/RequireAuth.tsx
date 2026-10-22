import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { useAppSelector } from '@/store/hooks/redux'

/** Без входа — на экран входа; после входа вернёт на исходный адрес. */
export const RequireAuth = ({ children }: { children: ReactNode }) => {
  const location = useLocation()
  const isAuthenticated = useAppSelector((state) => state.auth.isAuthenticated)

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
