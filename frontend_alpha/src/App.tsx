import { BrowserRouter } from 'react-router-dom'

import { useLoadCompany } from './hooks/useLoadCompany'
import { AppRoutes } from './routes'

const AppContent = () => {
  useLoadCompany()
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
