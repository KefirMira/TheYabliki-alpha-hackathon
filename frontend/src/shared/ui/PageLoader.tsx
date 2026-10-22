import { Loader2 } from 'lucide-react'

const PageLoader = () => (
  <div className="flex min-h-[40vh] items-center justify-center text-muted-foreground">
    <Loader2 className="h-6 w-6 animate-spin" aria-label="Загрузка" />
  </div>
)

export default PageLoader
