import { BrowserRouter } from 'react-router-dom'

// Каркас приложения: маршруты, лейаут и провайдеры появятся на следующих шагах.
const App = () => (
  <BrowserRouter
    future={{
      v7_startTransition: true,
      v7_relativeSplatPath: true,
    }}
  >
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-muted-foreground">Пульс бизнеса — каркас</p>
    </div>
  </BrowserRouter>
)

export default App
