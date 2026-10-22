import { type FormEvent, useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import { fieldClass, fieldLabelClass } from '@/shared/ui/fieldStyles'

import {
  type PasswordForm,
  passwordFormError,
  passwordRules,
  passwordStrength,
  STRENGTH_LABELS,
} from './passwordRules'

const STRENGTH_COLORS = ['#D5D7DB', '#B42318', '#8A5300', '#137A3D', '#137A3D']

const EMPTY: PasswordForm = { current: '', next: '', repeat: '' }

const PasswordInput = ({
  label,
  value,
  onChange,
  invalid,
  autoComplete,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  invalid: boolean
  autoComplete: string
}) => {
  const [visible, setVisible] = useState(false)
  return (
    <label className="flex flex-col gap-1.5">
      <span className={fieldLabelClass}>
        {label}
        <span className="text-brand"> *</span>
      </span>
      <span className="relative block">
        <input
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          autoComplete={autoComplete}
          className={fieldClass(invalid, 'pr-12')}
        />
        <button
          type="button"
          onClick={() => setVisible((current) => !current)}
          aria-label={visible ? 'Скрыть пароль' : 'Показать пароль'}
          className="absolute right-2 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg text-ink-3 hover:text-ink"
        >
          {visible ? (
            <EyeOff className="h-4 w-4" />
          ) : (
            <Eye className="h-4 w-4" />
          )}
        </button>
      </span>
    </label>
  )
}

interface ChangePasswordDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onChanged: () => void
}

/** Смена пароля. Заглушка: пароль никуда не отправляется. */
const ChangePasswordDialog = ({
  open,
  onOpenChange,
  onChanged,
}: ChangePasswordDialogProps) => {
  const [form, setForm] = useState<PasswordForm>(EMPTY)
  const [tried, setTried] = useState(false)

  const rules = passwordRules(form.next)
  const strength = passwordStrength(form.next)
  const error = passwordFormError(form)
  const mismatch = Boolean(form.repeat) && form.repeat !== form.next
  const showError = mismatch || (tried && Boolean(error))

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      setForm(EMPTY)
      setTried(false)
    }
    onOpenChange(next)
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (error) {
      setTried(true)
      return
    }
    handleOpenChange(false)
    onChanged()
  }

  const update = (key: keyof PasswordForm) => (value: string) =>
    setForm((current) => ({ ...current, [key]: value }))

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogTitle>Изменение пароля</DialogTitle>
        <DialogDescription>Пароль для входа в интернет-банк</DialogDescription>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <PasswordInput
            label="Текущий пароль"
            value={form.current}
            onChange={update('current')}
            invalid={tried && !form.current}
            autoComplete="current-password"
          />
          <div className="flex flex-col gap-2">
            <PasswordInput
              label="Новый пароль"
              value={form.next}
              onChange={update('next')}
              invalid={tried && !rules.every((rule) => rule.ok)}
              autoComplete="new-password"
            />
            <div className="flex items-center gap-3">
              <span className="flex flex-1 gap-1" aria-hidden="true">
                {[1, 2, 3, 4].map((bar) => (
                  <span
                    key={bar}
                    className="h-1 flex-1 rounded-sm"
                    style={{
                      background:
                        bar <= strength ? STRENGTH_COLORS[strength] : '#EAEBEE',
                    }}
                  />
                ))}
              </span>
              <span
                className="w-[72px] text-right text-xs font-semibold"
                style={{ color: STRENGTH_COLORS[strength] }}
              >
                {STRENGTH_LABELS[strength]}
              </span>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
              {rules.map((rule) => (
                <span
                  key={rule.label}
                  className={rule.ok ? 'text-tone-opp-fg' : 'text-ink-4'}
                >
                  {rule.ok ? '✓' : '·'} {rule.label}
                </span>
              ))}
            </div>
          </div>
          <PasswordInput
            label="Повторите новый пароль"
            value={form.repeat}
            onChange={update('repeat')}
            invalid={mismatch}
            autoComplete="new-password"
          />

          {showError && error && (
            <p className="text-sm text-tone-risk-fg" role="alert">
              {error}
            </p>
          )}

          <DialogFooter>
            <Button type="submit" className="h-auto px-[18px] py-3">
              Сохранить
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => handleOpenChange(false)}
              className={cn('h-auto px-[18px] py-3 font-medium')}
            >
              Отменить
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default ChangePasswordDialog
