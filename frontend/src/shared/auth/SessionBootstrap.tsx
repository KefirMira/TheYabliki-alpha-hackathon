import { useEffect } from 'react'
import { useAppDispatch } from '@/store/hooks/redux'
import { logout } from '@/store/reducers/AuthSlice'
import { restoreSession } from '@/store/service/Auth/signIn'
export const SessionBootstrap = () => {
  const dispatch = useAppDispatch()
  useEffect(() => {
    const expired = () => {
      dispatch(logout())
    }
    window.addEventListener('pulse-session-expired', expired)
    void dispatch(restoreSession())
    return () => window.removeEventListener('pulse-session-expired', expired)
  }, [dispatch])
  return null
}
