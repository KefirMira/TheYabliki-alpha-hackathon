import { BrowserRouter } from 'react-router-dom'

import { Toaster } from '@/components/ui/toaster'

import { useScrollTopOnNavigate } from './hooks/useScrollTopOnNavigate'
import { AppRoutes } from './routes'

const AppContent = () => {
  useScrollTopOnNavigate()
  return <AppRoutes />
}

const App = () => (
  <BrowserRouter
    future={{
      v7_startTransition: true,
      v7_relativeSplatPath: true,
    }}
  >
    <AppContent />
    <Toaster />
  </BrowserRouter>
)

export default App
