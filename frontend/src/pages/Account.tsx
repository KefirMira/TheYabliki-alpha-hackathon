import { useState } from 'react'
import { Lock, LogOut, Pencil, Shield, User } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { FEATURES } from '@/shared/constants/features'
import {
  DEMO_USER,
  type IPersonalData,
  PASSWORD_CHANGED_AT,
  ROLE_SPHERES,
} from '@/shared/mocks/pulse'
import Card from '@/shared/ui/Card'
import { toast } from '@/shared/ui/appToast'
import Tag from '@/shared/ui/Tag'
import { plural } from '@/shared/utils/plural'
import { useAppSelector } from '@/store/hooks/redux'
import { selectCompanyTitle } from '@/store/selectors/pulse'
import ChangePasswordDialog from '@/widgets/Account/ChangePasswordDialog'
import LogoutDialog from '@/widgets/Account/LogoutDialog'
import PersonalDataDialog from '@/widgets/Account/PersonalDataDialog'
import PageHeading from '@/widgets/Layout/PageHeading'

/** «14.05.1984 · 42 года» — возраст на дату прототипа. */
const birthWithAge = (birthDate: string) => {
  const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(birthDate)
  if (!match) return birthDate || '—'
  const [, day, month, year] = match.map(Number)
  const today = new Date()
  let age = today.getFullYear() - year
  if (
    today.getMonth() + 1 < month ||
    (today.getMonth() + 1 === month && today.getDate() < day)
  ) {
    age -= 1
  }
  return `${birthDate} · ${plural(age, ['год', 'года', 'лет'])}`
}

const Field = ({ label, value }: { label: string; value: string }) => (
  <div className="flex flex-col gap-0.5">
    <span className="text-[15px] text-ink-3">{label}</span>
    <span className="text-[17px] font-semibold">{value || '—'}</span>
  </div>
)

/**
 * Аккаунт и безопасность. Из сессии — только логин; личные данные и смена
 * пароля скрыты флагом, пока нет API пользователя.
 */
const Account = () => {
  const username = useAppSelector((state) => state.auth.username)
  const companyTitle = useAppSelector(selectCompanyTitle)
  const [person, setPerson] = useState<IPersonalData>(DEMO_USER)
  const [personalOpen, setPersonalOpen] = useState(false)
  const [passwordOpen, setPasswordOpen] = useState(false)

  const fullName = FEATURES.accountSettings
    ? [person.lastName, person.firstName, person.middleName]
        .filter(Boolean)
        .join(' ')
    : (username ?? 'Гость')
  const initials = FEATURES.accountSettings
    ? `${person.lastName[0] ?? ''}${person.firstName[0] ?? ''}`
    : fullName.slice(0, 2)

  return (
    <>
      <PageHeading
        title="Аккаунт и безопасность"
        subtitle={
          FEATURES.accountSettings
            ? 'Личные данные и пароль для входа'
            : 'Вход в интернет-банк и компания'
        }
      />

      <Card className="flex-row flex-wrap items-center gap-5 p-7">
        <span className="flex h-[72px] w-[72px] shrink-0 items-center justify-center rounded-3xl bg-surface-page text-2xl font-bold uppercase">
          {initials}
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <span className="text-2xl font-bold">{fullName}</span>
          <span className="inline-flex items-center gap-1.5 self-start rounded-lg px-2.5 py-1 text-sm text-ink-2 shadow-[inset_0_0_0_1px_#E6E7EA]">
            <Shield className="h-3.5 w-3.5" />
            {companyTitle}
          </span>
        </div>
        <LogoutDialog>
          <Button
            variant="outline"
            className="h-auto rounded-xl px-4 py-2.5 font-medium"
          >
            <LogOut className="rotate-180" />
            Выйти
          </Button>
        </LogoutDialog>
      </Card>

      <Card className="p-7">
        <div className="flex items-center gap-2.5">
          <h2 className="text-[17px] font-semibold">
            Аналитика под вашу сферу
          </h2>
          <Tag tone="muted" className="px-[7px] py-[3px]">
            Скоро
          </Tag>
        </div>
        <p className="-mt-1 text-[15px] text-ink-2">
          Пульс будет отбирать и объяснять события с учётом вашей зоны
          ответственности
        </p>
        <div className="flex flex-wrap gap-2">
          {ROLE_SPHERES.map((sphere) => (
            <span
              key={sphere}
              className="rounded-lg bg-surface-page px-3 py-1.5 text-sm text-ink-2"
            >
              {sphere}
            </span>
          ))}
        </div>
      </Card>

      {FEATURES.accountSettings && (
        <div className="grid items-start gap-4 lg:grid-cols-2">
          <Card className="gap-0 p-0">
            <div className="flex items-center justify-between gap-3 border-b border-line px-6 py-5">
              <h2 className="flex items-center gap-2.5 text-lg font-semibold">
                <User className="h-5 w-5" strokeWidth={1.8} />
                Личные данные
              </h2>
              <Button
                variant="secondary"
                onClick={() => setPersonalOpen(true)}
                className="h-auto px-3.5 py-2 text-[15px] font-medium"
              >
                <Pencil />
                Изменить
              </Button>
            </div>
            <div className="grid grid-cols-2 gap-x-8 gap-y-5 px-6 py-6">
              <Field label="Фамилия" value={person.lastName} />
              <Field label="Имя" value={person.firstName} />
              <Field label="Отчество" value={person.middleName} />
              <Field
                label="Дата рождения"
                value={birthWithAge(person.birthDate)}
              />
              <Field label="Телефон" value={person.phone} />
              <Field label="Почта" value={person.email} />
            </div>
          </Card>

          <Card className="gap-0 p-0">
            <div className="border-b border-line px-6 py-5">
              <h2 className="flex items-center gap-2.5 text-lg font-semibold">
                <Lock className="h-5 w-5" strokeWidth={1.8} />
                Безопасность
              </h2>
            </div>
            <div className="flex flex-col gap-3 px-6 py-6">
              <span className="text-[17px] font-semibold">Пароль</span>
              <button
                type="button"
                onClick={() => setPasswordOpen(true)}
                className="flex h-[52px] items-center justify-center rounded-xl bg-surface-page text-[15px] font-semibold transition-colors hover:bg-surface-chip"
              >
                Изменить пароль
              </button>
              <span className="text-[15px] text-ink-3">
                Последнее изменение — {PASSWORD_CHANGED_AT}
              </span>
            </div>
          </Card>
        </div>
      )}

      <PersonalDataDialog
        open={personalOpen}
        data={person}
        onOpenChange={setPersonalOpen}
        onSave={(data) => {
          setPerson(data)
          toast.success('Личные данные сохранены')
        }}
      />
      <ChangePasswordDialog
        open={passwordOpen}
        onOpenChange={setPasswordOpen}
        onChanged={() => toast.success('Пароль изменён')}
      />
    </>
  )
}

export default Account
