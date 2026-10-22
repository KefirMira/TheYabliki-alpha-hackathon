import type { ReactNode } from 'react'
import {
  AlertTriangle,
  FileText,
  Quote,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'

import { cn } from '@/lib/utils'
import AlfaLogo from '@/shared/ui/AlfaLogo'
import Card from '@/shared/ui/Card'
import ImpactBars from '@/shared/ui/ImpactBars'
import LayerTag, { type InfoLayer } from '@/shared/ui/LayerTag'
import Tag from '@/shared/ui/Tag'
import type {
  IBankPosition,
  IInsightDetail,
  ScenarioLikelihood,
} from '@/store/models/IPulse'
import { LEVEL_LABEL } from '@/widgets/Insights/insightView'

/** Заголовок блока инсайта с тегом слоя справа. */
const SectionCard = ({
  title,
  layer,
  className,
  children,
}: {
  title: string
  layer?: InfoLayer
  className?: string
  children: ReactNode
}) => (
  <Card className={className}>
    <div className="flex items-center gap-2.5">
      <h2 className="text-[17px] font-semibold leading-6">{title}</h2>
      {layer && <LayerTag layer={layer} />}
    </div>
    {children}
  </Card>
)

export const WhatHappened = ({ detail }: { detail: IInsightDetail }) => (
  <SectionCard title="Что произошло" layer="fact">
    <p className="whitespace-pre-line text-[15px] leading-[23px] text-pretty">
      {detail.fact}
    </p>
  </SectionCard>
)

export const WhatItMeans = ({ detail }: { detail: IInsightDetail }) => (
  <SectionCard title="Что это значит для компании" layer="ai">
    <p className="text-[15px] leading-[23px] text-pretty">{detail.impact}</p>
    {detail.figures.length > 0 && (
      <div className="mt-auto grid grid-cols-2 gap-3">
        {detail.figures.map((figure) => (
          <div
            key={figure.label}
            className="flex flex-col gap-0.5 rounded-[14px] bg-surface-page px-3.5 py-3"
          >
            <span className="whitespace-nowrap text-[22px] font-bold tracking-[-0.01em]">
              {figure.value}
            </span>
            <span className="text-[13px] text-ink-3">{figure.label}</span>
          </div>
        ))}
      </div>
    )}
  </SectionCard>
)

/**
 * «Как это оценивает Альфа-Банк» — обязательный блок. Если позиции по теме
 * нет, это говорится явно, а не умалчивается.
 */
export const BankPosition = ({ bank }: { bank: IBankPosition | null }) => {
  if (!bank) {
    return (
      <div className="col-span-full flex min-w-0 gap-[18px] rounded-3xl bg-surface-cell py-5 pl-5 pr-6 shadow-[inset_0_0_0_1px_#E6E7EA]">
        <span className="w-[3px] shrink-0 rounded-sm bg-line-dashed" />
        <div className="flex min-w-0 flex-1 flex-col gap-2.5">
          <div className="flex items-center gap-2.5">
            <h2 className="text-[17px] font-semibold leading-6 text-ink-2">
              Как это оценивает Альфа-Банк
            </h2>
            <LayerTag layer="bank" muted />
          </div>
          <p className="text-[15px] leading-[23px] text-ink-2">
            По этой теме у Альфа-Банка нет опубликованной позиции. Вывод основан
            на внешних источниках.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="col-span-full flex min-w-0 gap-[18px] rounded-3xl bg-white py-5 pl-5 pr-6">
      <span className="w-[3px] shrink-0 rounded-sm bg-brand" />
      <div className="flex min-w-0 flex-1 flex-col gap-3.5">
        <div className="flex items-center gap-2.5">
          <h2 className="text-[17px] font-semibold leading-6">
            Как это оценивает Альфа-Банк
          </h2>
          <LayerTag layer="bank" />
        </div>
        <div className="flex items-center gap-2.5">
          <AlfaLogo className="h-7 w-7 rounded-full" />
          <span className="flex flex-col gap-px">
            <span className="text-sm font-semibold">Позиция Альфа-Банка</span>
            <span className="text-[13px] text-ink-3">
              {[bank.author, bank.date].filter(Boolean).join(' · ')}
            </span>
          </span>
        </div>
        <p className="max-w-[1000px] text-lg leading-[27px] text-pretty">
          «{bank.quote}»
        </p>
        {bank.change && (
          <div className="flex flex-wrap items-center gap-3 self-start rounded-xl bg-surface-cell px-3.5 py-2.5 text-sm">
            <span className="text-ink-2">{bank.change.label}:</span>
            <span className="text-ink-3 line-through">
              {bank.change.previous}
            </span>
            <span>→</span>
            <span className="font-bold">{bank.change.current}</span>
          </div>
        )}
        {bank.document && (
          <div className="flex items-center gap-2 border-t border-line-soft pt-3 text-[13px] text-ink-3">
            <FileText className="h-4 w-4 shrink-0" />
            <span className="min-w-0 truncate">{bank.document}</span>
          </div>
        )}
      </div>
    </div>
  )
}

export const Affected = ({ detail }: { detail: IInsightDetail }) => (
  <SectionCard title="Что затронуто">
    <div className="flex flex-col gap-2.5">
      {detail.affected.map((item) => (
        <div
          key={item.name}
          className="grid grid-cols-[minmax(0,1fr)_120px] items-center gap-3"
        >
          <span className="flex min-w-0 flex-col gap-px">
            <span className="text-[15px] font-semibold">{item.name}</span>
            <span className="truncate text-[13px] text-ink-3">
              {item.description}
            </span>
          </span>
          <span className="flex items-center justify-end gap-2">
            <ImpactBars level={item.level} />
            <span className="w-[62px] text-[13px] text-ink-2">
              {LEVEL_LABEL[item.level]}
            </span>
          </span>
        </div>
      ))}
    </div>
  </SectionCard>
)

const PointList = ({
  title,
  items,
  icon: Icon,
  iconClass,
}: {
  title: string
  items: string[]
  icon: typeof TrendingUp
  iconClass: string
}) => (
  <div className="flex flex-col gap-2">
    <span className="text-xs font-semibold tracking-[0.06em] text-ink-3">
      {title}
    </span>
    {items.map((item) => (
      <span
        key={item}
        className="grid grid-cols-[16px_minmax(0,1fr)] items-start gap-2.5 text-[15px] leading-[22px] text-pretty"
      >
        <Icon className={cn('mt-[3px] h-4 w-4', iconClass)} />
        {item}
      </span>
    ))}
  </div>
)

/** Риски и возможности списком — как их вернул анализ. */
export const RisksOpportunities = ({ detail }: { detail: IInsightDetail }) => (
  <SectionCard title="Риски и возможности" layer="ai">
    {detail.risks.length > 0 && (
      <PointList
        title="РИСКИ"
        items={detail.risks}
        icon={TrendingDown}
        iconClass="text-tone-risk-fg"
      />
    )}
    {detail.opportunities.length > 0 && (
      <PointList
        title="ВОЗМОЖНОСТИ"
        items={detail.opportunities}
        icon={TrendingUp}
        iconClass="text-tone-opp-fg"
      />
    )}
  </SectionCard>
)

export const Actions = ({ detail }: { detail: IInsightDetail }) => (
  <SectionCard title="Что можно сделать" layer="ai">
    <div className="flex flex-col gap-2">
      {detail.actions.map((action) =>
        action.offer ? (
          <div
            key={action.title}
            className="flex flex-col gap-1.5 rounded-[14px] px-3.5 py-3 shadow-[inset_0_0_0_1px_#E6E7EA]"
          >
            <div>
              <Tag tone="offer" className="px-[7px] py-[3px]">
                Предложение банка
              </Tag>
            </div>
            <span className="text-[15px] font-semibold text-pretty">
              {action.title}
            </span>
            {action.description && (
              <span className="text-[13px] text-ink-2">
                {action.description}
              </span>
            )}
            <span className="text-xs leading-4 text-ink-3">
              Предложение носит информационный характер и не является
              обязательным. Не является индивидуальной инвестиционной
              рекомендацией.
            </span>
          </div>
        ) : (
          <div
            key={action.title}
            className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-[14px] bg-surface-page py-3 pl-3.5 pr-3"
          >
            <span className="flex min-w-0 flex-col gap-px">
              <span className="text-[15px] font-semibold text-pretty">
                {action.title}
              </span>
              {action.description && (
                <span className="text-[13px] text-ink-3">
                  {action.description}
                </span>
              )}
            </span>
            {action.cta && (
              <span className="cursor-pointer whitespace-nowrap rounded-[10px] bg-white px-3 py-[7px] text-[13px] font-semibold">
                {action.cta}
              </span>
            )}
          </div>
        )
      )}
    </div>
  </SectionCard>
)

const LIKELIHOOD_STYLE: Record<ScenarioLikelihood, string> = {
  Вероятно: 'bg-ink text-white',
  Возможно: 'bg-surface-chip text-ink',
  Маловероятно: 'bg-white text-ink-2 shadow-[inset_0_0_0_1px_#DADBDF]',
}

/** Сценарии без выдуманных вероятностей: метка + сила данных и основание. */
export const Scenarios = ({ detail }: { detail: IInsightDetail }) => (
  <SectionCard title="Сценарии" layer="hyp">
    <div className="flex flex-col gap-2.5">
      {detail.scenarios.map((scenario) => (
        <div
          key={scenario.text}
          className="grid grid-cols-[112px_minmax(0,1fr)] items-center gap-3 border-t border-line-soft pt-2.5"
        >
          <span
            className={cn(
              'rounded-lg py-[5px] text-center text-[13px] font-semibold',
              LIKELIHOOD_STYLE[scenario.likelihood]
            )}
          >
            {scenario.likelihood}
          </span>
          <span className="flex min-w-0 flex-col gap-[3px]">
            <span className="text-[15px] leading-[21px] text-pretty">
              {scenario.text}
            </span>
            <span className="text-[13px] leading-[18px] text-ink-3">
              Сила данных:{' '}
              <b className="font-semibold text-ink">{scenario.strength}</b> —{' '}
              {scenario.basis}
            </span>
          </span>
        </div>
      ))}
    </div>
  </SectionCard>
)

/** Источники и итог проверки достоверности — без выдуманных процентов. */
export const Sources = ({ detail }: { detail: IInsightDetail }) => {
  const hasWarnings = detail.warnings.length > 0

  return (
    <SectionCard title="Источники и проверка">
      {detail.sources.length > 0 ? (
        <div className="flex flex-col gap-2.5">
          {detail.sources.map((source, index) => (
            <div
              key={`${source.name}-${index}`}
              className="grid grid-cols-[32px_minmax(0,1fr)] items-center gap-3"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-surface-page text-ink-2">
                <FileText className="h-4 w-4" />
              </span>
              <span className="flex min-w-0 flex-col gap-px">
                <span className="truncate text-[15px] font-semibold">
                  {source.name}
                </span>
                {source.description && (
                  <span className="truncate text-[13px] text-ink-3">
                    {source.description}
                  </span>
                )}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-[15px] text-ink-2">
          Источники для этого инсайта не найдены.
        </p>
      )}
      {detail.confidence && (
        <div
          className={cn(
            'mt-auto flex flex-col gap-1.5 rounded-xl px-3 py-2.5 text-sm',
            hasWarnings ? 'bg-tone-risk' : 'bg-surface-page'
          )}
        >
          <span className="flex items-center gap-2">
            {hasWarnings ? (
              <AlertTriangle className="h-4 w-4 shrink-0 text-tone-risk-fg" />
            ) : (
              <ShieldCheck className="h-4 w-4 shrink-0 text-tone-opp-fg" />
            )}
            <span>
              Проверка достоверности:{' '}
              <b className="font-semibold">{detail.confidence}</b>
            </span>
          </span>
          {detail.warnings.map((warning) => (
            <span key={warning} className="pl-6 text-[13px] text-ink-2">
              {warning}
            </span>
          ))}
        </div>
      )}
    </SectionCard>
  )
}

/** Фрагменты-доказательства: точный текст из материалов, без пересказа. */
export const Evidence = ({ detail }: { detail: IInsightDetail }) => (
  <SectionCard
    title="На чём основан вывод"
    layer="fact"
    className="col-span-full"
  >
    <div className="flex flex-col gap-3">
      {detail.evidence.map((item, index) => (
        <figure
          key={`${item.document}-${item.page}-${index}`}
          className="flex flex-col gap-1.5 rounded-[14px] bg-surface-page px-4 py-3"
        >
          <blockquote className="flex gap-2.5 text-[15px] leading-[23px] text-pretty">
            <Quote className="mt-1 h-4 w-4 shrink-0 text-ink-3" />
            <span className="min-w-0">{item.text}</span>
          </blockquote>
          {(item.document || item.page) && (
            <figcaption className="pl-[26px] text-[13px] text-ink-3">
              {[item.document, item.page && `стр. ${item.page}`]
                .filter(Boolean)
                .join(' · ')}
            </figcaption>
          )}
        </figure>
      ))}
    </div>
  </SectionCard>
)
