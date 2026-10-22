import { useState } from 'react'
import { Check, Pencil } from 'lucide-react'

import { Button } from '@/components/ui/button'
import Card from '@/shared/ui/Card'
import { fieldClass } from '@/shared/ui/fieldStyles'

const NOTES_LIMIT = 2000

/** «Дополнительные сведения» — своими словами то, чего нет в данных банка. */
const ContextNotes = ({ onSaved }: { onSaved: (message: string) => void }) => {
  const [notes, setNotes] = useState('')
  const [draft, setDraft] = useState<string | null>(null)
  const editing = draft !== null
  const changed = editing && draft !== notes

  const send = () => {
    if (!changed) return
    setNotes(draft)
    setDraft(null)
    onSaved('Сведения отправлены — Пульс учтёт их в следующих инсайтах')
  }

  return (
    <Card>
      <div className="flex flex-col gap-1">
        <h2 className="text-[17px] font-semibold leading-6">
          Дополнительные сведения
        </h2>
        <p className="text-[15px] text-ink-2">
          Опишите своими словами то, чего нет в данных банка — поставщики,
          покупатели, конкуренты, планы
        </p>
      </div>

      {editing ? (
        <>
          <textarea
            autoFocus
            value={draft}
            onChange={(event) =>
              setDraft(event.target.value.slice(0, NOTES_LIMIT))
            }
            rows={4}
            aria-label="Дополнительные сведения о компании"
            className={fieldClass(
              false,
              'h-auto resize-y px-5 py-4 text-base leading-[26px]'
            )}
          />
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex-1 text-[13px] tabular-nums text-ink-3">
              Пульс учитывает этот текст при отборе новостей и расчёте влияния ·{' '}
              {draft.length} / {NOTES_LIMIT}
            </span>
            <Button
              variant="ghost"
              onClick={() => setDraft(notes)}
              className="h-auto px-3.5 py-[9px] text-sm font-medium"
            >
              Сбросить
            </Button>
            <Button
              variant="secondary"
              onClick={() => setDraft(null)}
              className="h-auto px-3.5 py-[9px] text-sm font-medium"
            >
              Отмена
            </Button>
            <Button
              onClick={send}
              disabled={!changed}
              className="h-auto px-3.5 py-[9px] text-sm"
            >
              Отправить
            </Button>
          </div>
        </>
      ) : (
        <>
          <p className="rounded-[14px] bg-surface-page px-5 py-4 text-base leading-[26px] text-pretty">
            {notes || 'Сведения не добавлены'}
          </p>
          <div className="flex items-center gap-2">
            <Check className="h-4 w-4 text-tone-opp-fg" />
            <span className="flex-1 text-sm text-ink-3">
              Учитывается при отборе новостей и расчёте влияния
            </span>
            <Button
              variant="secondary"
              onClick={() => setDraft(notes)}
              className="h-auto px-3.5 py-[9px] text-[15px] font-medium"
            >
              <Pencil />
              Изменить
            </Button>
          </div>
        </>
      )}
    </Card>
  )
}

export default ContextNotes
