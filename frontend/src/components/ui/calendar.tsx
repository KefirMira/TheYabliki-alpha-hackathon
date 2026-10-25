import * as React from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import {
  type CaptionProps,
  DayPicker,
  type DayPickerSingleProps,
  useNavigation,
} from 'react-day-picker'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'

/** Календарь выбора одной даты. */
export type CalendarProps = Omit<DayPickerSingleProps, 'mode'>

/** Новости — с 2000 года по следующий: дальше выбирать нечего. */
const FIRST_YEAR = 2000

/**
 * Заголовок календаря: месяц и год выбираются из списков, а не листаются
 * по одному месяцу. Списки без портала — они внутри поповера календаря.
 */
const MonthYearCaption = ({ displayMonth }: CaptionProps) => {
  const { goToMonth } = useNavigation()
  const year = displayMonth.getFullYear()
  const month = displayMonth.getMonth()

  const years = React.useMemo(() => {
    const last = Math.max(new Date().getFullYear() + 1, year)
    const first = Math.min(FIRST_YEAR, year)
    return Array.from({ length: last - first + 1 }, (_, i) => last - i)
  }, [year])

  return (
    <div className="flex items-center justify-center gap-2 pb-3 pt-1">
      <Select
        value={String(month)}
        onValueChange={(value) => goToMonth(new Date(year, Number(value), 1))}
      >
        <SelectTrigger aria-label="Месяц" className="h-9 w-[132px] capitalize">
          <SelectValue>
            {format(displayMonth, 'LLLL', { locale: ru })}
          </SelectValue>
        </SelectTrigger>
        <SelectContent portalled={false}>
          {Array.from({ length: 12 }, (_, index) => (
            <SelectItem
              key={index}
              value={String(index)}
              className="capitalize"
            >
              {format(new Date(year, index, 1), 'LLLL', { locale: ru })}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select
        value={String(year)}
        onValueChange={(value) => goToMonth(new Date(Number(value), month, 1))}
      >
        <SelectTrigger aria-label="Год" className="h-9 w-[92px]">
          <SelectValue>{year}</SelectValue>
        </SelectTrigger>
        <SelectContent portalled={false}>
          {years.map((option) => (
            <SelectItem key={option} value={String(option)}>
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

/**
 * Календарь на react-day-picker: неделя с понедельника, русская локаль,
 * выбранный день — цветом бренда, сегодняшний — подложкой.
 */
const Calendar = ({
  className,
  classNames,
  showOutsideDays = true,
  selected,
  ...props
}: CalendarProps) => {
  // Месяц показа — выбранной даты; после выбора другой даты — её месяц.
  const [month, setMonth] = React.useState<Date>(selected ?? new Date())
  React.useEffect(() => {
    if (selected) setMonth(selected)
  }, [selected])

  return (
    <DayPicker
      mode="single"
      locale={ru}
      weekStartsOn={1}
      showOutsideDays={showOutsideDays}
      month={month}
      onMonthChange={setMonth}
      selected={selected}
      className={cn('p-3', className)}
      classNames={{
        months: 'flex flex-col',
        month: 'space-y-2',
        caption: 'relative flex items-center justify-center',
        nav: 'hidden',
        table: 'w-full border-collapse',
        head_row: 'flex',
        head_cell: 'w-10 text-[13px] font-normal capitalize text-ink-3',
        row: 'mt-1 flex w-full',
        cell: 'relative h-10 w-10 p-0 text-center text-sm',
        day: 'h-10 w-10 rounded-xl p-0 font-normal transition-colors hover:bg-surface-page focus-visible:shadow-[inset_0_0_0_1.5px_#121316] focus-visible:outline-none',
        day_selected:
          '!bg-primary font-semibold !text-primary-foreground hover:!bg-primary',
        day_today: 'bg-surface-page font-semibold',
        day_outside: 'text-ink-4',
        day_disabled: 'pointer-events-none text-ink-4 opacity-50',
        day_hidden: 'invisible',
        ...classNames,
      }}
      components={{
        IconLeft: () => <ChevronLeft className="h-4 w-4" />,
        IconRight: () => <ChevronRight className="h-4 w-4" />,
        Caption: MonthYearCaption,
      }}
      {...props}
    />
  )
}

export { Calendar }
