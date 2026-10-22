import { type FormEvent, useState } from 'react'
import { ArrowRight, Check, CircleAlert, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import BackLink from '@/shared/ui/BackLink'
import Card from '@/shared/ui/Card'
import { fieldClass } from '@/shared/ui/fieldStyles'
import { useAppDispatch, useAppSelector } from '@/store/hooks/redux'
import { clearAnalysis } from '@/store/reducers/AnalysisSlice'
import { runAnalysis } from '@/store/service/Insights/runAnalysis'
import { FeedMessage } from '@/widgets/Insights/FeedStates'

const TEXT_LIMIT = 5000

const HOW_IT_WORKS = [
  [
    'Найдёт подтверждения',
    'Подберёт фрагменты из аналитики банка и других материалов базы знаний',
  ],
  ['Сопоставит с компанией', 'Учтёт профиль компании из Альфа-Бизнеса'],
  [
    'Подготовит инсайт',
    'Риски, возможности и что можно сделать — со ссылками на источники',
  ],
]

/**
 * Анализ своей новости: `POST /analyses`. Запрос синхронный — шагов агента
 * API не отдаёт, поэтому прогресс показываем без выдуманных этапов.
 * Состояние запуска — в сторе по компании: пока анализ идёт, второй не
 * запустить ни «Очистить», ни уходом со страницы.
 * В демо-режиме бэкенд отвечает AI_DISABLED_IN_DEMO — показываем как есть.
 */
const AnalyzeNews = () => {
  const dispatch = useAppDispatch()
  const companyId = useAppSelector((state) => state.company.currentCompanyId)
  const run = useAppSelector((state) =>
    companyId ? state.analysis.byCompany[companyId] : undefined
  )
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [tried, setTried] = useState(false)

  const running = run?.status === 'running'
  const invalid = tried && (!title.trim() || !text.trim())

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (running || !companyId) return
    if (!title.trim() || !text.trim()) {
      setTried(true)
      return
    }
    setTried(false)
    dispatch(runAnalysis({ companyId, title: title.trim(), text: text.trim() }))
  }

  const handleClear = () => {
    if (running) return
    setTitle('')
    setText('')
    setTried(false)
    if (companyId) dispatch(clearAnalysis(companyId))
  }

  return (
    <>
      <BackLink to="/pulse/insights">Все инсайты</BackLink>

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card className="gap-5 p-7">
          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            <div className="flex flex-col gap-1.5">
              <h1 className="text-[26px] font-bold leading-[1.2]">
                Проанализировать новость
              </h1>
              <p className="max-w-[640px] text-[15px] leading-[22px] text-ink-2">
                Добавьте новость, которой нет в ленте, — Пульс оценит, как она
                влияет на вашу компанию, и подготовит инсайт
              </p>
            </div>

            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-semibold">
                Заголовок новости<span className="text-brand"> *</span>
              </span>
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Например, Минэнерго предложило ограничить экспорт дизельного топлива"
                className={fieldClass(tried && !title.trim())}
              />
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-semibold">
                Текст или описание новости<span className="text-brand"> *</span>
              </span>
              <textarea
                value={text}
                onChange={(event) =>
                  setText(event.target.value.slice(0, TEXT_LIMIT))
                }
                rows={7}
                placeholder="Вставьте текст новости целиком или опишите своими словами, что произошло"
                className={fieldClass(
                  tried && !text.trim(),
                  'h-auto resize-y py-3 leading-[23px]'
                )}
              />
              <span className="text-right text-[13px] tabular-nums text-ink-3">
                {text.length} / {TEXT_LIMIT}
              </span>
            </label>

            {invalid && (
              <p className="flex items-center gap-2 text-sm text-tone-risk-fg">
                <CircleAlert className="h-4 w-4" />
                Заполните заголовок и текст новости
              </p>
            )}

            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Button
                type="submit"
                disabled={running || !companyId}
                className="h-auto px-[18px] py-3 text-[15px]"
              >
                {running ? 'Анализируем…' : 'Проанализировать'}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={handleClear}
                disabled={running}
                className="h-auto px-[18px] py-3 text-[15px] font-medium"
              >
                Очистить
              </Button>
              <span className="text-[13px] text-ink-3">
                Обычно занимает до минуты
              </span>
            </div>
          </form>
        </Card>

        <div className="flex min-w-0 flex-col gap-4">
          {!run && (
            <Card className="gap-3.5">
              <h2 className="text-[17px] font-semibold leading-6">
                Как это работает
              </h2>
              {HOW_IT_WORKS.map(([heading, description], index) => (
                <div
                  key={heading}
                  className="grid grid-cols-[28px_minmax(0,1fr)] items-start gap-3"
                >
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-surface-page text-[13px] font-bold">
                    {index + 1}
                  </span>
                  <span className="flex flex-col gap-0.5">
                    <span className="text-[15px] font-semibold">{heading}</span>
                    <span className="text-sm leading-5 text-ink-2">
                      {description}
                    </span>
                  </span>
                </div>
              ))}
            </Card>
          )}

          {run?.status === 'running' && (
            <Card className="gap-3" aria-live="polite">
              <h2 className="flex items-center gap-2.5 text-[17px] font-semibold leading-6">
                <Loader2 className="h-5 w-5 animate-spin" />
                Анализируем новость
              </h2>
              <p className="text-sm leading-5 text-ink-2">
                Пульс ищет подтверждения в базе знаний и сопоставляет новость с
                профилем компании. Можно перейти в другой раздел — анализ не
                прервётся, результат появится здесь и в ленте.
              </p>
            </Card>
          )}

          {run?.status === 'error' && (
            <FeedMessage
              error
              title={run.demo ? 'Анализ выключен в демо' : 'Анализ не выполнен'}
              text={
                run.demo
                  ? `${run.message}. Готовые инсайты — в ленте.`
                  : run.message
              }
              action={
                run.demo && (
                  <Button asChild variant="secondary" className="mt-1">
                    <Link to="/pulse/insights">Открыть ленту</Link>
                  </Button>
                )
              }
            />
          )}

          {run?.status === 'done' && (
            <Card className="gap-3.5">
              <div className="flex items-center gap-2.5">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-tone-opp-fg text-white">
                  <Check className="h-3.5 w-3.5" strokeWidth={2.5} />
                </span>
                <h2 className="text-[17px] font-semibold leading-6">
                  Инсайт готов
                </h2>
              </div>
              <div className="flex flex-col gap-2 rounded-2xl p-4 shadow-[inset_0_0_0_1px_#E6E7EA]">
                <span className="text-[17px] font-semibold leading-6 text-pretty">
                  {run.title}
                </span>
                {run.result.analysis.summary && (
                  <span className="text-sm leading-5 text-ink-2">
                    {run.result.analysis.summary}
                  </span>
                )}
              </div>
              <Button asChild className="h-auto py-3 text-[15px]">
                <Link to={`/pulse/insights/${run.result.insight_id}`}>
                  Открыть инсайт
                  <ArrowRight />
                </Link>
              </Button>
              <span className="text-[13px] text-ink-3">
                Инсайт сохранён и добавлен в ленту
              </span>
            </Card>
          )}
        </div>
      </div>
    </>
  )
}

export default AnalyzeNews
