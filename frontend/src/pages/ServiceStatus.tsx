import { useEffect, useState } from 'react'
import { CheckCircle2, CircleSlash, ExternalLink, RotateCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useReadiness } from '@/hooks/useReadiness'
import { cn } from '@/lib/utils'
import { fetchApiVersion, swaggerUrl } from '@/shared/api/system.api'
import Card from '@/shared/ui/Card'
import PageHeading from '@/widgets/Layout/PageHeading'

const MODE_TEXT = {
  available: 'Полный: анализ новостей через модель включён',
  demo: 'Демо: данные синтетические, анализ через модель выключен',
  unknown: 'Не удалось определить',
} as const

const CheckRow = ({
  ok,
  title,
  okText,
  offText,
}: {
  ok: boolean
  title: string
  okText: string
  offText: string
}) => (
  <div className="flex items-start gap-3 border-t border-line-soft pt-3 first:border-t-0 first:pt-0">
    {ok ? (
      <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-tone-opp-fg" />
    ) : (
      <CircleSlash className="mt-0.5 h-5 w-5 shrink-0 text-ink-3" />
    )}
    <span className="flex flex-col gap-0.5">
      <span className="text-[15px] font-semibold">{title}</span>
      <span className={cn('text-sm', ok ? 'text-ink-2' : 'text-ink-3')}>
        {ok ? okText : offText}
      </span>
    </span>
  </div>
)

/**
 * Состояние сервиса для экспертов: что сейчас работает на бэкенде
 * (`/ready`), версия API и Swagger. Объясняет демо-режим, чтобы
 * выключенный анализ не принимали за поломку.
 */
const ServiceStatus = () => {
  const { readiness, error, loading, ai, reload } = useReadiness()
  const [version, setVersion] = useState<string | null>(null)

  useEffect(() => {
    let stale = false
    fetchApiVersion()
      .then((value) => !stale && setVersion(value))
      .catch(() => !stale && setVersion(null))
    return () => {
      stale = true
    }
  }, [])

  const checks = readiness?.checks

  return (
    <>
      <PageHeading
        title="Состояние сервиса"
        subtitle="Что сейчас работает в Пульсе и в каком режиме"
      />

      <Card className="gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-col gap-0.5">
            <span className="text-[13px] text-ink-3">Режим</span>
            <span className="text-[17px] font-semibold">
              {loading ? 'Проверяем…' : MODE_TEXT[ai]}
            </span>
          </div>
          <Button
            variant="secondary"
            onClick={reload}
            disabled={loading}
            className="h-auto px-3.5 py-2 text-sm font-medium"
          >
            <RotateCw className={loading ? 'animate-spin' : undefined} />
            Проверить снова
          </Button>
        </div>

        {error && !loading && (
          <p className="rounded-xl bg-tone-risk px-3.5 py-2.5 text-sm text-tone-risk-fg">
            {error}
          </p>
        )}

        {checks && (
          <div className="flex flex-col gap-3">
            <CheckRow
              ok={checks.database}
              title="База данных"
              okText="Профили компаний и инсайты доступны"
              offText="Недоступна — профили и лента не загрузятся"
            />
            <CheckRow
              ok={checks.llm_config}
              title="Модель для анализа"
              okText="Настроена — можно анализировать новости"
              offText="Не подключена — анализ новостей выключен"
            />
            <CheckRow
              ok={checks.rag}
              title="База знаний аналитики банка"
              okText="Подключена — инсайты опираются на аналитику Альфа-Банка"
              offText="Не подключена — позиции банка в новых инсайтах не будет"
            />
          </div>
        )}
      </Card>

      <Card className="flex-row flex-wrap items-center justify-between gap-3">
        <span className="flex flex-col gap-0.5">
          <span className="text-[13px] text-ink-3">API бэкенда</span>
          <span className="text-[15px] font-semibold">
            {version ? `Версия ${version}` : 'Версия неизвестна'}
          </span>
        </span>
        <Button
          asChild
          variant="secondary"
          className="h-auto px-3.5 py-2 text-sm font-medium"
        >
          <a href={swaggerUrl()} target="_blank" rel="noreferrer">
            Документация API (Swagger)
            <ExternalLink />
          </a>
        </Button>
      </Card>
    </>
  )
}

export default ServiceStatus
