import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import Card from '@/shared/ui/Card'

const NotFound = () => (
  <Card className="items-center gap-3 py-14 text-center">
    <p className="text-lg font-semibold">Страница не найдена</p>
    <Button asChild variant="secondary">
      <Link to="/">На главную</Link>
    </Button>
  </Card>
)

export default NotFound
