import { Link, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import PulseLogo from '@/shared/ui/PulseLogo'
import { plural } from '@/shared/utils/plural'
import { useAppSelector } from '@/store/hooks/redux'
import { selectPulseInsights } from '@/store/selectors/pulse'
import InsightKindTag from '@/widgets/Insights/InsightKindTag'
import { filterFeed, filtersFromParams } from '@/widgets/Insights/feedFilter'

const WIDGET_COUNT = 3

// Колонок столько, сколько инсайтов: карточки всегда во всю ширину виджета.
const COLUMNS: Record<number, string> = {
  1: 'md:grid-cols-1',
  2: 'md:grid-cols-2',
  3: 'md:grid-cols-3',
}

/**
 * Точка входа в Пульс на главной банка: самое важное событие одной строкой
 * и три важных инсайта из API. Стоит в первом экране, заметнее промо.
 */
const PulseWidget = () => {
  const navigate = useNavigate()
  const companyId = useAppSelector((state) => state.company.currentCompanyId)
  const { loadingList, isInitialized, error } = useAppSelector(
    (state) => state.insights
  )
  const all = useAppSelector(selectPulseInsights)
  const insights = filterFeed(
    all,
    filtersFromParams(new URLSearchParams()),
    []
  ).items.slice(0, WIDGET_COUNT)

  const teaser = (() => {
    if (!companyId) return 'Компания не выбрана'
    if (loadingList || !isInitialized) return 'Загружаем инсайты…'
    if (error) return 'Инсайты не загрузились — откройте Пульс, чтобы повторить'
    if (insights.length === 0) return 'Инсайтов пока нет'
    return `Сегодня важно: ${insights[0].title}`
  })()

  return (
    <section className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-6 gap-y-5 rounded-3xl bg-white px-6 py-5">
      <Link to="/pulse/summary" className="flex min-w-0 items-center gap-3.5">
        <PulseLogo />
        <span className="flex min-w-0 flex-col gap-0.5">
          <span className="flex items-center gap-2.5">
            <span className="text-[17px] font-bold">Пульс бизнеса</span>
            {all.length > 0 && (
              <span className="flex h-5 items-center rounded-full bg-brand px-[7px] text-[11px] font-bold text-white">
                {plural(all.length, ['инсайт', 'инсайта', 'инсайтов'])}
              </span>
            )}
          </span>
          <span className="truncate text-[15px] text-ink-2">{teaser}</span>
        </span>
      </Link>

      <Button onClick={() => navigate('/pulse/summary')}>Открыть Пульс</Button>

      {insights.length > 0 && (
        <div
          className={cn(
            'col-span-full -mx-5 grid border-t border-line pt-4',
            COLUMNS[insights.length]
          )}
        >
          {insights.map((insight, index) => (
            <Link
              key={insight.id}
              to={`/pulse/insights/${insight.id}`}
              className={cn(
                'flex min-w-0 flex-col gap-2 px-5 py-1 transition-opacity hover:opacity-80',
                index < insights.length - 1 && 'md:border-r md:border-line'
              )}
            >
              <div>
                <InsightKindTag insight={insight} />
              </div>
              <span className="line-clamp-2 text-[15px] font-semibold leading-5">
                {insight.title}
              </span>
            </Link>
          ))}
        </div>
      )}
    </section>
  )
}

export default PulseWidget
