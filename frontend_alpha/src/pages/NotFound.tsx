import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'

const NotFound = () => (
  <div className="flex flex-col items-center gap-3 rounded-lg bg-card px-6 py-14 text-center">
    <p className="text-lg font-semibold">Страница не найдена</p>
    <Button asChild variant="secondary">
      <Link to="/insights">К ленте инсайтов</Link>
    </Button>
  </div>
)

export default NotFound
