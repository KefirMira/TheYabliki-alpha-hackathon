import { type FormEvent, useState } from 'react'
import { Navigate, type Path, useLocation, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import AlfaLogo from '@/shared/ui/AlfaLogo'
import { fieldClass, fieldLabelClass } from '@/shared/ui/fieldStyles'
import { useAppDispatch, useAppSelector } from '@/store/hooks/redux'
import { signIn } from '@/store/service/Auth/signIn'
const Login = () => {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const location = useLocation()
  const { isAuthenticated, checking } = useAppSelector((state) => state.auth)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const saved = (location.state as { from?: Partial<Path> } | null)?.from
  const from =
    saved?.pathname?.startsWith('/') &&
    !saved.pathname.startsWith('//') &&
    saved.pathname !== '/login'
      ? saved
      : '/'
  if (checking) return <p role="status">Проверяем сессию…</p>
  if (isAuthenticated) return <Navigate to={from} replace />
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (busy) return
    if (!username.trim() || !password) {
      setError('Введите логин и пароль')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await dispatch(signIn(username.trim(), password))
      setPassword('')
      navigate(from, { replace: true })
    } catch (reason) {
      setError((reason as Error).message)
      setPassword('')
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-page p-4">
      <form
        onSubmit={submit}
        className="flex w-full max-w-[440px] flex-col gap-6 rounded-3xl bg-white p-6 sm:p-10"
      >
        <span className="flex items-center gap-2.5">
          <AlfaLogo className="h-9 w-9 rounded-[10px]" />
          <span className="text-xl font-bold">Альфа-Бизнес</span>
        </span>
        <h1 className="text-[28px] font-bold">Вход в интернет-банк</h1>
        <p className="text-sm text-ink-3">
          Синтетическое интеграционное демо. Нужна серверная учётная запись и её
          пароль.
        </p>
        <label className="flex flex-col gap-1.5">
          <span className={fieldLabelClass}>Логин</span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            className={fieldClass(false, 'h-[52px] px-4 text-base')}
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className={fieldLabelClass}>Пароль</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            className={fieldClass(false, 'h-[52px] px-4 text-base')}
          />
        </label>
        {error && (
          <p role="alert" className="text-tone-risk-fg">
            {error}
          </p>
        )}
        <Button type="submit" disabled={busy} size="lg">
          {busy ? 'Проверяем…' : 'Войти'}
        </Button>
      </form>
    </div>
  )
}
export default Login
