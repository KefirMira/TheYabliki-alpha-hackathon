import { AlertTriangle, AlignLeft, Check } from 'lucide-react'

import { cn } from '@/lib/utils'
import Card from '@/shared/ui/Card'
import type { IInsightDetail } from '@/store/models/IPulse'

const AnalysisLog = ({ detail }: { detail: IInsightDetail }) => (
  <div className="flex flex-col gap-3.5">
    <span className="text-[13px] text-ink-3">
      {detail.savedPilot
        ? 'Исторический trace пилота от ' +
          detail.savedPilot.pilotDate +
          '. Время импорта: ' +
          detail.logTime
        : 'Как Пульс пришёл к выводу · ' + detail.logTime}
    </span>
    {detail.log.map((step) => (
      <div
        key={step.title}
        className="grid grid-cols-[24px_minmax(0,1fr)] items-start gap-3"
      >
        <span
          className={cn(
            'flex h-6 w-6 items-center justify-center rounded-full',
            step.warning
              ? 'bg-tone-risk text-tone-risk-fg'
              : 'bg-tone-opp text-tone-opp-fg'
          )}
        >
          {step.warning ? (
            <AlertTriangle className="h-3.5 w-3.5" strokeWidth={2.5} />
          ) : (
            <Check className="h-3.5 w-3.5" strokeWidth={2.5} />
          )}
        </span>
        <span className="flex min-w-0 flex-col gap-0.5">
          <span className="text-[15px] font-medium leading-5">
            {step.title}
          </span>
          <span className="break-words text-[13px] text-ink-3">
            {step.description}
          </span>
        </span>
      </div>
    ))}
  </div>
)

/** Правая панель инсайта: ход анализа — как Пульс пришёл к выводу. */
const InsightSidePanel = ({ detail }: { detail: IInsightDetail }) => (
  <Card className="2xl:sticky 2xl:top-4">
    <h2 className="flex items-center gap-2 text-[17px] font-semibold">
      <AlignLeft className="h-4 w-4" />
      Сведения о сохранённом анализе
    </h2>
    <AnalysisLog detail={detail} />
  </Card>
)

export default InsightSidePanel
