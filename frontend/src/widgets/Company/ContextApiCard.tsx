import { Braces, Code } from 'lucide-react'

import logo1c from '@/assets/logo-1c.png'
import logoBitrix from '@/assets/logo-bitrix.png'
import logoSap from '@/assets/logo-sap.png'
import { cn } from '@/lib/utils'
import { API_DATA_TYPES, API_SAMPLE } from '@/shared/mocks/pulse'
import Card from '@/shared/ui/Card'
import PulseLogo from '@/shared/ui/PulseLogo'
import Tag from '@/shared/ui/Tag'

const SYSTEM_LOGOS = [
  { src: logo1c, alt: '1С', className: 'bg-[#FFF200]' },
  { src: logoSap, alt: 'SAP', className: 'bg-white' },
  { src: logoBitrix, alt: '1С-Битрикс', className: 'bg-white' },
]

const DashedArrow = () => (
  <span className="flex items-center gap-1 text-ink-4" aria-hidden="true">
    <span className="w-8 border-t-[1.5px] border-dashed border-current" />
    <span className="text-xs">›</span>
  </span>
)

/**
 * «Открытый API контекста» — анонс. Единая схема данных для файлов, ручного
 * ввода и любых учётных систем; подключение появится позже.
 */
const ContextApiCard = () => (
  <Card className="grid gap-6 p-5 md:p-7 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)]">
    <div className="flex flex-col justify-center gap-3">
      <div className="flex items-center gap-2.5">
        <h2 className="text-[17px] font-semibold leading-6">
          Открытый API контекста
        </h2>
        <Tag tone="muted" className="px-[7px] py-[3px]">
          Скоро
        </Tag>
      </div>
      <p className="text-[15px] leading-[26px] text-ink-2 text-pretty">
        Единая схема данных компании для любых систем. Подключите учётную
        систему, CRM или собственную разработку — Пульс получит контрагентов,
        договоры, кредитный портфель и планы
      </p>
      <span className="text-[13px] text-ink-3">
        Подключение по единому API — скоро
      </span>
    </div>

    <div className="flex min-w-0 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        {SYSTEM_LOGOS.map((logo) => (
          <span
            key={logo.alt}
            className={cn(
              'flex h-11 w-11 items-center justify-center overflow-hidden rounded-xl p-1.5 shadow-[inset_0_0_0_1px_#E6E7EA]',
              logo.className
            )}
          >
            <img
              src={logo.src}
              alt={logo.alt}
              className="max-h-full max-w-full"
            />
          </span>
        ))}
        <span className="flex h-11 items-center gap-1.5 rounded-xl px-3 text-[13px] font-medium shadow-[inset_0_0_0_1px_#E6E7EA]">
          <Code className="h-4 w-4" />
          Ваша система
        </span>
        <DashedArrow />
        <span className="flex h-11 items-center gap-2 rounded-xl bg-ink px-4 text-[13px] font-semibold text-white">
          <Braces className="h-4 w-4" />
          API контекста
        </span>
        <DashedArrow />
        <PulseLogo className="h-9 w-9" />
      </div>

      <div className="flex flex-wrap gap-1.5">
        {API_DATA_TYPES.map((type) => (
          <span
            key={type}
            className="rounded-lg bg-surface-page px-3 py-1.5 text-[13px] text-ink-2"
          >
            {type}
          </span>
        ))}
      </div>

      <pre className="overflow-x-auto rounded-[14px] bg-surface-page px-4 py-3.5 font-mono text-xs leading-5 text-ink-2">
        {API_SAMPLE}
      </pre>
    </div>
  </Card>
)

export default ContextApiCard
