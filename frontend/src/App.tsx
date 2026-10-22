import { BrowserRouter } from 'react-router-dom'

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
  </BrowserRouter>
)

export default App
