import { type ReactNode, useState } from 'react'
import { ChevronDown } from 'lucide-react'

import { cn } from '@/lib/utils'
import { DIGEST_TIMES } from '@/shared/mocks/pulse'
import Card from '@/shared/ui/Card'
import Segmented from '@/shared/ui/Segmented'
import Switch from '@/shared/ui/Switch'
import PageHeading from '@/widgets/Layout/PageHeading'

const SettingRow = ({
  title,
  description,
  control,
  divided = false,
}: {
  title: string
  description: string
  control: ReactNode
  divided?: boolean
}) => (
  <div
    className={cn(
      'flex flex-wrap items-center justify-between gap-4',
      divided && 'border-t border-line pt-4'
    )}
  >
    <div className="flex min-w-0 flex-col gap-0.5">
      <span className="text-[17px] font-medium">{title}</span>
      <span className="text-[15px] text-ink-3">{description}</span>
    </div>
    {control}
  </div>
)

type PushMode = 'high' | 'all'

/** Настройки Пульса. Пока UI-заглушка: значения живут на этой странице. */
const PulseSettings = () => {
  const [horizon, setHorizon] = useState<'now' | 'm3' | 'm12'>('now')
  const [time, setTime] = useState('09:00')
  const [days, setDays] = useState<'work' | 'all'>('work')
  const [push, setPush] = useState(true)
  const [pushMode, setPushMode] = useState<PushMode>('high')

  return (
    <>
      <PageHeading
        title="Настройки Пульса"
        subtitle="Что отслеживать и как сообщать о новых инсайтах"
      />

      <Card className="p-6">
        <SettingRow
          title="Горизонт по умолчанию"
          description="Применяется к ленте инсайтов и Сводке"
          control={
            <Segmented
              label="Горизонт по умолчанию"
              value={horizon}
              onChange={setHorizon}
              options={[
                { value: 'now', label: 'Сейчас' },
                { value: 'm3', label: '3 мес' },
                { value: 'm12', label: '12 мес' },
              ]}
            />
          }
        />
      </Card>

      <Card className="p-6">
        <h2 className="border-b border-line pb-4 text-[17px] font-semibold">
          Сводка дня
        </h2>
        <SettingRow
          title="Время"
          description="По московскому времени"
          control={
            <label className="relative">
              <span className="sr-only">Время сводки дня</span>
              <select
                value={time}
                onChange={(event) => setTime(event.target.value)}
                className="h-12 w-[174px] appearance-none rounded-xl bg-surface-page pl-4 pr-10 text-base outline-none md:text-[15px] focus:shadow-[inset_0_0_0_1.5px_#121316]"
              >
                {DIGEST_TIMES.map((option) => (
                  <option key={option}>{option}</option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2" />
            </label>
          }
        />
        <SettingRow
          divided
          title="Дни"
          description="Когда присылать сводку"
          control={
            <Segmented
              label="Дни сводки"
              value={days}
              onChange={setDays}
              options={[
                { value: 'work', label: 'Будни' },
                { value: 'all', label: 'Каждый день' },
              ]}
            />
          }
        />
      </Card>

      <Card className="p-6">
        <h2 className="border-b border-line pb-4 text-[17px] font-semibold">
          Уведомления
        </h2>
        <SettingRow
          title="Лента в интернет-банке"
          description="Новые инсайты всегда появляются во вкладке «Инсайты»"
          control={
            <span className="flex items-center gap-3 text-sm text-ink-3">
              Всегда
              <Switch checked locked label="Лента в интернет-банке" />
            </span>
          }
        />
        <SettingRow
          divided
          title="Push-уведомления"
          description="В мобильном приложении Альфа-Бизнес"
          control={
            <Switch
              checked={push}
              onChange={setPush}
              label="Push-уведомления"
            />
          }
        />
        {push && (
          <div
            role="radiogroup"
            aria-label="Какие инсайты присылать"
            className="flex flex-wrap gap-x-8 gap-y-3"
          >
            {(
              [
                ['high', 'Только высокое влияние'],
                ['all', 'Все новые инсайты'],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={pushMode === value}
                onClick={() => setPushMode(value)}
                className="flex items-center gap-2.5 text-[17px]"
              >
                <span
                  className={cn(
                    'flex h-5 w-5 items-center justify-center rounded-full',
                    pushMode === value
                      ? 'shadow-[inset_0_0_0_2px_#121316]'
                      : 'shadow-[inset_0_0_0_2px_#B8BABF]'
                  )}
                >
                  {pushMode === value && (
                    <span className="h-2.5 w-2.5 rounded-full bg-ink" />
                  )}
                </span>
                {label}
              </button>
            ))}
          </div>
        )}
      </Card>
    </>
  )
}

export default PulseSettings
