import { type FormEvent, useState } from 'react'
import { Navigate, type Path, useLocation, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { DEMO_ACCOUNTS } from '@/shared/constants/accounts'
import AlfaLogo from '@/shared/ui/AlfaLogo'
import { fieldClass, fieldLabelClass } from '@/shared/ui/fieldStyles'
import { useAppDispatch, useAppSelector } from '@/store/hooks/redux'
import { signIn } from '@/store/service/Auth/signIn'

/**
 * Вход в интернет-банк. Авторизации в API пока нет: логин сверяется со
 * списком тестовых учёток сборки (VITE_DEMO_ACCOUNTS), пароль не
 * проверяется. Компанию не выбираем — она определяется по логину. Без
 * учёток подходит любой непустой логин.
 */
const Login = () => {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const location = useLocation()
  const isAuthenticated = useAppSelector((state) => state.auth.isAuthenticated)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [tried, setTried] = useState(false)
  const [unknown, setUnknown] = useState(false)

  // Вернуть туда, откуда отправили на вход, иначе — на главную банка.
  // Целиком, с search и hash: в адресе живут фильтры ленты.
  const saved = (location.state as { from?: Partial<Path> } | null)?.from
  const from: Partial<Path> | undefined = saved && {
    pathname: saved.pathname,
    search: saved.search,
    hash: saved.hash,
  }

  if (isAuthenticated) return <Navigate to={from ?? '/'} replace />

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!username.trim()) {
      setTried(true)
      return
    }
    if (!dispatch(signIn(username.trim()))) {
      setUnknown(true)
      return
    }
    navigate(from ?? '/', { replace: true })
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-page p-4">
      <form
        onSubmit={handleSubmit}
        className="flex w-full max-w-[440px] flex-col gap-6 rounded-3xl bg-white p-6 sm:p-10"
      >
        <span className="flex items-center gap-2.5">
          <AlfaLogo className="h-9 w-9 rounded-[10px]" />
          <span className="text-xl font-bold tracking-[-0.01em]">
            Альфа-Бизнес
          </span>
        </span>

        <h1 className="text-[28px] font-bold leading-[1.2]">
          Вход в интернет-банк
        </h1>

        <div className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5">
            <span className={fieldLabelClass}>Логин</span>
            <input
              value={username}
              onChange={(event) => {
                setUsername(event.target.value)
                setUnknown(false)
              }}
              autoComplete="username"
              className={fieldClass(
                (tried && !username.trim()) || unknown,
                'h-[52px] px-4 text-base'
              )}
            />
            {tried && !username.trim() && (
              <span className="text-[13px] text-tone-risk-fg">
                Введите логин
              </span>
            )}
            {unknown && (
              <span className="text-[13px] text-tone-risk-fg">
                Такого логина нет. Используйте один из тестовых ниже
              </span>
            )}
          </label>
          <label className="flex flex-col gap-1.5">
            <span className={fieldLabelClass}>Пароль</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              className={fieldClass(false, 'h-[52px] px-4 text-base')}
            />
          </label>
        </div>

        <Button type="submit" size="lg" className="h-auto py-4 text-base">
          Войти
        </Button>

        {DEMO_ACCOUNTS.length > 0 ? (
          <div className="flex flex-col gap-2 rounded-2xl bg-surface-page p-4 text-sm">
            <span className="font-semibold">Тестовые логины</span>
            <span className="flex flex-wrap gap-1.5">
              {DEMO_ACCOUNTS.map((account) => (
                <button
                  key={account.login}
                  type="button"
                  onClick={() => {
                    setUsername(account.login)
                    setUnknown(false)
                  }}
                  className="rounded-lg bg-white px-2.5 py-1 font-mono text-[13px] transition-colors hover:bg-surface-chip"
                >
                  {account.login}
                  <span className="ml-1.5 font-sans text-ink-3">
                    {account.companyIds.length}
                  </span>
                </button>
              ))}
            </span>
            <span className="text-[13px] text-ink-3">
              Число — сколько компаний доступно логину. Пароль не проверяется:
              это демо-вход до подключения авторизации.
            </span>
          </div>
        ) : (
          <span className="cursor-default text-center text-[15px] font-medium">
            Восстановить доступ
          </span>
        )}
      </form>
    </div>
  )
}

export default Login
