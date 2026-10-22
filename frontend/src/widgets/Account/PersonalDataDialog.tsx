import { type FormEvent, useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from '@/components/ui/dialog'
import type { IPersonalData } from '@/shared/mocks/pulse'
import { fieldClass, fieldLabelClass } from '@/shared/ui/fieldStyles'

const FIELDS: {
  key: keyof IPersonalData
  label: string
  required?: boolean
}[] = [
  { key: 'lastName', label: 'Фамилия', required: true },
  { key: 'firstName', label: 'Имя', required: true },
  { key: 'middleName', label: 'Отчество' },
  { key: 'birthDate', label: 'Дата рождения' },
  { key: 'phone', label: 'Телефон', required: true },
  { key: 'email', label: 'Почта' },
]

interface PersonalDataDialogProps {
  open: boolean
  data: IPersonalData
  onOpenChange: (open: boolean) => void
  onSave: (data: IPersonalData) => void
}

/** Изменение личных данных. Обязательны фамилия, имя и телефон. */
const PersonalDataDialog = ({
  open,
  data,
  onOpenChange,
  onSave,
}: PersonalDataDialogProps) => {
  const [draft, setDraft] = useState(data)
  const [tried, setTried] = useState(false)

  // Каждое открытие начинается с актуальных данных.
  useEffect(() => {
    if (open) {
      setDraft(data)
      setTried(false)
    }
  }, [open, data])

  const missing = FIELDS.filter(
    (field) => field.required && !draft[field.key].trim()
  )

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (missing.length) {
      setTried(true)
      return
    }
    const trimmed = Object.fromEntries(
      Object.entries(draft).map(([key, value]) => [key, value.trim()])
    ) as unknown as IPersonalData
    onSave(trimmed)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[600px]">
        <DialogTitle>Изменение личных данных</DialogTitle>
        <DialogDescription>
          Данные видны администраторам компании
        </DialogDescription>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <div className="grid gap-4 sm:grid-cols-2">
            {FIELDS.map((field) => (
              <label key={field.key} className="flex flex-col gap-1.5">
                <span className={fieldLabelClass}>
                  {field.label}
                  {field.required && <span className="text-brand"> *</span>}
                </span>
                <input
                  value={draft[field.key]}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      [field.key]: event.target.value,
                    }))
                  }
                  className={fieldClass(
                    tried && Boolean(field.required) && !draft[field.key].trim()
                  )}
                />
              </label>
            ))}
          </div>

          {tried && missing.length > 0 && (
            <p className="text-sm text-tone-risk-fg" role="alert">
              Заполните обязательные поля
            </p>
          )}

          <DialogFooter>
            <Button type="submit" className="h-auto px-[18px] py-3">
              Сохранить
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => onOpenChange(false)}
              className="h-auto px-[18px] py-3 font-medium"
            >
              Отменить
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default PersonalDataDialog
