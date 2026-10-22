import { type FormEvent, useState } from 'react'
import {
  AlertTriangle,
  AlignLeft,
  ArrowUp,
  Check,
  MessageSquare,
} from 'lucide-react'

import { cn } from '@/lib/utils'
import { FEATURES } from '@/shared/constants/features'
import Card from '@/shared/ui/Card'
import Segmented, { type SegmentedOption } from '@/shared/ui/Segmented'
import type { IInsightDetail, IInsightQuestion } from '@/store/models/IPulse'

type PanelTab = 'log' | 'ask'

/** Ответ на свой вопрос — заглушка до подключения ассистента. */
const STUB_ANSWER =
  'Свободные вопросы Пульс начнёт разбирать после подключения ассистента. Пока выберите один из вопросов выше.'

const PANEL_TABS: SegmentedOption<PanelTab>[] = [
  { value: 'log', label: 'Ход анализа', icon: AlignLeft },
  { value: 'ask', label: 'Спросить', icon: MessageSquare },
]

const AnalysisLog = ({ detail }: { detail: IInsightDetail }) => (
  <div className="flex flex-col gap-3.5">
    <span className="text-[13px] text-ink-3">
      Как Пульс пришёл к выводу · {detail.logTime}
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

/** Чат по инсайту: подсказки-вопросы и последний ответ. */
const AskPulse = ({ questions }: { questions: IInsightQuestion[] }) => {
  const [active, setActive] = useState<IInsightQuestion>(questions[0])
  const [draft, setDraft] = useState('')

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    const question = draft.trim()
    if (!question) return
    const known = questions.find(
      (item) => item.question.toLowerCase() === question.toLowerCase()
    )
    setActive(known ?? { question, answer: STUB_ANSWER })
    setDraft('')
  }

  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex flex-wrap gap-1.5">
        {questions.map((item) => (
          <button
            key={item.question}
            type="button"
            onClick={() => setActive(item)}
            className={cn(
              'rounded-[10px] px-2.5 py-[7px] text-left text-[13px] font-medium transition-colors',
              active.question === item.question
                ? 'bg-ink text-white'
                : 'bg-surface-page hover:bg-surface-chip'
            )}
          >
            {item.question}
          </button>
        ))}
      </div>

      <div className="max-w-[85%] self-end rounded-2xl rounded-br-[4px] bg-ink px-3.5 py-2.5 text-[15px] leading-[21px] text-white">
        {active.question}
      </div>
      <div className="flex max-w-[92%] flex-col gap-1.5">
        <div className="rounded-2xl rounded-bl-[4px] bg-surface-page px-3.5 py-3 text-[15px] leading-[22px] text-pretty">
          {active.answer}
        </div>
        <span className="text-[13px] text-ink-3">
          Пульс · по данным компании и источникам инсайта
        </span>
      </div>

      <form
        onSubmit={handleSubmit}
        className="mt-2 flex h-[52px] items-center gap-2 rounded-[14px] bg-surface-page pl-4 pr-1.5"
      >
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Задайте вопрос об этом инсайте"
          aria-label="Вопрос об инсайте"
          className="min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-ink-4"
        />
        <button
          type="submit"
          aria-label="Отправить вопрос"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand text-white transition-colors hover:bg-brand-hover"
        >
          <ArrowUp className="h-5 w-5" />
        </button>
      </form>
    </div>
  )
}

/**
 * Правая панель инсайта: прозрачность вывода и вопросы к нему. Чата в API
 * пока нет — без него панель показывает только ход анализа.
 */
const InsightSidePanel = ({ detail }: { detail: IInsightDetail }) => {
  const [tab, setTab] = useState<PanelTab>('log')
  const withChat = FEATURES.insightChat && detail.questions.length > 0

  if (!withChat) {
    return (
      <Card className="2xl:sticky 2xl:top-4">
        <h2 className="flex items-center gap-2 text-[17px] font-semibold">
          <AlignLeft className="h-4 w-4" />
          Ход анализа
        </h2>
        <AnalysisLog detail={detail} />
      </Card>
    )
  }

  return (
    <Card className="2xl:sticky 2xl:top-4">
      <Segmented
        fill
        label="Разделы панели"
        options={PANEL_TABS}
        value={tab}
        onChange={setTab}
      />
      {tab === 'log' ? (
        <AnalysisLog detail={detail} />
      ) : (
        <AskPulse questions={detail.questions} />
      )}
    </Card>
  )
}

export default InsightSidePanel
