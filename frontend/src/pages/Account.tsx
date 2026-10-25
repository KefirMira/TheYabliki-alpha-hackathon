import { LogOut, Shield } from 'lucide-react'

import { Button } from '@/components/ui/button'
import Card from '@/shared/ui/Card'
import { useAppSelector } from '@/store/hooks/redux'
import { selectCompanyTitle } from '@/store/selectors/pulse'
import LogoutDialog from '@/widgets/Account/LogoutDialog'
import PageHeading from '@/widgets/Layout/PageHeading'

/**
 * Аккаунт: логин сессии, выбранная компания и выход. Личных данных и смены
 * пароля нет — у бэкенда пока нет API пользователя.
 */
const Account = () => {
  const username = useAppSelector((state) => state.auth.username) ?? 'Гость'
  const companyTitle = useAppSelector(selectCompanyTitle)

  return (
    <>
      <PageHeading
        title="Аккаунт и безопасность"
        subtitle="Вход в интернет-банк и компания"
      />

      <Card className="flex-row flex-wrap items-center gap-5 p-5 md:p-7">
        <span className="flex h-[72px] w-[72px] shrink-0 items-center justify-center rounded-3xl bg-surface-page text-2xl font-bold uppercase">
          {username.slice(0, 2)}
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <span className="text-2xl font-bold">{username}</span>
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
    </>
  )
}

export default Account
