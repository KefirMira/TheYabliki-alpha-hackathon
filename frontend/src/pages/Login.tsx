import { type FormEvent, useState } from 'react'
import { Navigate, type Path, useLocation, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import AlfaLogo from '@/shared/ui/AlfaLogo'
import { fieldClass, fieldLabelClass } from '@/shared/ui/fieldStyles'
import { useAppDispatch, useAppSelector } from '@/store/hooks/redux'
import { login } from '@/store/reducers/AuthSlice'

/**
 * Вход в интернет-банк. Заглушка: авторизации в API пока нет, подходит любой
 * непустой логин — «Войти» сразу открывает банк. Компанию не выбираем — она
 * определяется по логину.
 */
const Login = () => {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const location = useLocation()
  const isAuthenticated = useAppSelector((state) => state.auth.isAuthenticated)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [tried, setTried] = useState(false)

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
    dispatch(login(username.trim()))
    navigate(from ?? '/', { replace: true })
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-page p-4">
      <form
        onSubmit={handleSubmit}
        className="flex w-full max-w-[440px] flex-col gap-6 rounded-[20px] bg-white p-10"
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
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              className={fieldClass(
                tried && !username.trim(),
                'h-[52px] px-4 text-base'
              )}
            />
            {tried && !username.trim() && (
              <span className="text-[13px] text-tone-risk-fg">
                Введите логин
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

        <span className="cursor-default text-center text-[15px] font-medium">
          Восстановить доступ
        </span>
      </form>
    </div>
  )
}

export default Login
