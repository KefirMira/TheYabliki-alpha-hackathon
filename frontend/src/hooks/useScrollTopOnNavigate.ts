import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

/** При переходе на другой экран — к началу страницы, как в интернет-банке. */
export const useScrollTopOnNavigate = () => {
  const { pathname } = useLocation()

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
}
