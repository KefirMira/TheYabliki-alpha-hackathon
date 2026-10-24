import { type FormEvent, useState } from 'react'
import { ArrowRight, Check, CircleAlert, Info, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { useReadiness } from '@/hooks/useReadiness'
import {
  NEWS_DIAGNOSTIC_LABEL,
  type NewsFormValues,
  newsFormError,
  newsKeyOf,
} from '@/shared/api/news.api'
import BackLink from '@/shared/ui/BackLink'
import Card from '@/shared/ui/Card'
import DatePickerInput from '@/shared/ui/DatePickerInput'
import { fieldClass } from '@/shared/ui/fieldStyles'
import TimePickerInput from '@/shared/ui/TimePickerInput'
import { composeDateTime } from '@/shared/utils/dateTimeInput'
import { useAppDispatch, useAppSelector } from '@/store/hooks/redux'
import { clearAnalysis } from '@/store/reducers/AnalysisSlice'
import { runAnalysis } from '@/store/service/Insights/runAnalysis'
import AiDemoNotice from '@/widgets/Analysis/AiDemoNotice'
import OtherCompaniesAnalysis from '@/widgets/Analysis/OtherCompaniesAnalysis'
import { FeedMessage } from '@/widgets/Insights/FeedStates'

/** Предел текста новости в API приёма (docs/NEWS_INGESTION_API.md). */
const TEXT_LIMIT = 100000
const TITLE_LIMIT = 500

const EMPTY_FORM: NewsFormValues = {
  title: '',
  content: '',
  url: '',
  publishedAt: '',
  synthetic: false,
}

const HOW_IT_WORKS = [
  [
    'Сохранит новость',
    'В базу Пульса — повторно та же новость не задвоится, и её можно разобрать для любой вашей компании',
  ],
  [
    'Найдёт подтверждения',
    'Подберёт фрагменты из аналитики банка и других материалов базы знаний',
  ],
  [
    'Подготовит инсайт',
    'Риски, возможности и что можно сделать для компании — со ссылками на источники',
  ],
]

const RUNNING_TEXT = {
  saving: {
    title: 'Сохраняем новость',
    text: 'Новость попадёт в базу Пульса — затем начнётся анализ.',
  },
  analyzing: {
    title: 'Анализируем новость',
    text: 'Пульс ищет подтверждения в базе знаний и сопоставляет новость с профилем компании.',
  },
}

/**
 * Анализ новости для компании. Новость сначала сохраняется в базу
 * (`POST /api/news`, без ИИ), затем разбирается для компании
 * (`POST .../news/{news_id}/analyses`). Так та же новость не задваивается,
 * готовый разбор не запускает LLM повторно, а после результата новость
 * можно разобрать для других компаний логина. Состояние — в сторе по
 * компании: пока анализ идёт, второй не запустить ни «Очистить», ни уходом
 * со страницы. В демо-режиме анализ выключен заранее, по `/ready`.
 */
const AnalyzeNews = () => {
  const dispatch = useAppDispatch()
  const companyId = useAppSelector((state) => state.company.currentCompanyId)
  const run = useAppSelector((state) =>
    companyId ? state.analysis.byCompany[companyId] : undefined
  )
  const { ai } = useReadiness()
  const aiOff = ai === 'demo'
  const [form, setForm] = useState<NewsFormValues>(EMPTY_FORM)
  const [tried, setTried] = useState(false)
  // Дата и время публикации — как напечатаны, «ДД.ММ.ГГГГ» и «ЧЧ:ММ».
  const [date, setDate] = useState('')
  const [time, setTime] = useState('')

  // Тип новости задаёт режим сервиса, а не пользователь: в демо бэкенд
  // примет только синтетическую, в полном — обычную.
  const publishedAt = composeDateTime(date, time)
  const news: NewsFormValues = {
    ...form,
    publishedAt: publishedAt ?? '',
    synthetic: aiOff,
  }
  const formError = () =>
    newsFormError(news) ??
    (publishedAt === null
      ? 'Дата публикации — в формате ДД.ММ.ГГГГ, время — ЧЧ:ММ'
      : null)

  const set = <K extends keyof NewsFormValues>(
    key: K,
    value: NewsFormValues[K]
  ) => setForm((current) => ({ ...current, [key]: value }))

  const running = run?.status === 'running'
  const error = tried ? formError() : null

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (running || !companyId || aiOff) return
    if (formError()) {
      setTried(true)
      return
    }
    setTried(false)
    const newsKey = newsKeyOf(news)
    const title = form.title.trim()
    // Та же новость уже сохранена (например, упал анализ) — второй раз в
    // базу не отправляем, разбираем сохранённую.
    if (run?.newsId && run.newsKey === newsKey) {
      dispatch(runAnalysis({ companyId, title, newsId: run.newsId, newsKey }))
    } else {
      dispatch(runAnalysis({ companyId, title, form: news, newsKey }))
    }
  }

  const handleClear = () => {
    if (running) return
    setForm(EMPTY_FORM)
    setDate('')
    setTime('')
    setTried(false)
    if (companyId) dispatch(clearAnalysis(companyId))
  }

  return (
    <>
      <BackLink to="/pulse/insights">Все инсайты</BackLink>

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card className="gap-5 p-5 md:p-7">
          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            <div className="flex flex-col gap-1.5">
              <h1 className="text-[26px] font-bold leading-[1.2]">
                Проанализировать новость
              </h1>
              <p className="max-w-[640px] text-[15px] leading-[22px] text-ink-2">
                Добавьте новость, которой нет в ленте, — Пульс сохранит её,
                оценит, как она влияет на вашу компанию, и подготовит инсайт
              </p>
            </div>

            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-semibold">
                Заголовок новости<span className="text-brand"> *</span>
              </span>
              <input
                value={form.title}
                onChange={(event) =>
                  set('title', event.target.value.slice(0, TITLE_LIMIT))
                }
                placeholder="Например, Минэнерго предложило ограничить экспорт дизельного топлива"
                className={fieldClass(tried && !form.title.trim())}
              />
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-semibold">
                Текст новости<span className="text-brand"> *</span>
              </span>
              <textarea
                value={form.content}
                onChange={(event) =>
                  set('content', event.target.value.slice(0, TEXT_LIMIT))
                }
                rows={7}
                placeholder="Вставьте текст новости целиком или опишите своими словами, что произошло"
                className={fieldClass(
                  tried && !form.content.trim(),
                  'h-auto resize-y py-3 leading-[23px]'
                )}
              />
            </label>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-semibold">
                  Ссылка на источник
                </span>
                <input
                  value={form.url}
                  onChange={(event) => set('url', event.target.value)}
                  placeholder="https://"
                  inputMode="url"
                  className={fieldClass(false)}
                />
                <span className="text-[13px] text-ink-3">
                  Необязательно. По ссылке Пульс узнает новость при повторной
                  загрузке
                </span>
              </label>
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="news-published-date"
                  className="text-sm font-semibold"
                >
                  Дата и время публикации
                </label>
                <div className="grid grid-cols-[minmax(0,1fr)_104px] gap-2">
                  <DatePickerInput
                    id="news-published-date"
                    value={date}
                    onChange={setDate}
                    invalid={tried && publishedAt === null}
                    disabledDates={{ after: new Date() }}
                  />
                  <TimePickerInput
                    value={time}
                    onChange={setTime}
                    invalid={tried && publishedAt === null}
                  />
                </div>
                <span className="text-[13px] text-ink-3">
                  Необязательно. Без времени — начало дня
                </span>
              </div>
            </div>

            {error && (
              <p className="flex items-center gap-2 text-sm text-tone-risk-fg">
                <CircleAlert className="h-4 w-4 shrink-0" />
                {error}
              </p>
            )}

            {aiOff && <AiDemoNotice />}

            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Button
                type="submit"
                disabled={running || !companyId || aiOff}
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
                {RUNNING_TEXT[run.stage].title}
              </h2>
              <p className="text-sm leading-5 text-ink-2">
                {RUNNING_TEXT[run.stage].text} Можно перейти в другой раздел —
                анализ не прервётся, результат появится здесь и в ленте.
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
                  : run.newsId
                    ? `${run.message}. Новость сохранена — при повторе она не задвоится.`
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
            <Card className="gap-3.5" aria-live="polite">
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
              {run.duplicate && (
                <div className="flex gap-2.5 text-sm leading-5 text-ink-2">
                  <Info className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>
                    Такая новость уже была в базе — использована сохранённая
                    {run.diagnostics.length > 0 &&
                      `, она не перезаписана: ${run.diagnostics
                        .map((code) => NEWS_DIAGNOSTIC_LABEL[code])
                        .join('; ')}`}
                    .
                  </span>
                </div>
              )}
              <Button asChild className="h-auto py-3 text-[15px]">
                <Link to={`/pulse/insights/${run.result.insight_id}`}>
                  Открыть инсайт
                  <ArrowRight />
                </Link>
              </Button>
              <span className="text-[13px] text-ink-3">
                Инсайт сохранён и добавлен в ленту
              </span>
              {run.newsId && (
                <OtherCompaniesAnalysis
                  newsId={run.newsId}
                  newsKey={run.newsKey}
                  title={run.title}
                />
              )}
            </Card>
          )}
        </div>
      </div>
    </>
  )
}

export default AnalyzeNews
