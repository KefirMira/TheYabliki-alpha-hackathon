import { Construction } from 'lucide-react'

/** Заглушка разделов, которые ещё не подключены к API. */
const InProgress = () => (
  <div className="flex flex-col items-center gap-3 rounded-lg bg-card px-6 py-14 text-center">
    <Construction
      className="h-8 w-8 text-muted-foreground"
      aria-hidden="true"
    />
    <p className="font-semibold">Раздел в разработке</p>
    <p className="max-w-md text-sm text-muted-foreground">
      Пока доступна вкладка «Инсайты».
    </p>
  </div>
)

export default InProgress
