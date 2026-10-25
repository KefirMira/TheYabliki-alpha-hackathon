import { useState, type ReactElement } from 'react'
import { useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { useAppDispatch } from '@/store/hooks/redux'
import { signOut } from '@/store/service/Auth/signIn'

/**
 * Подтверждение выхода. children — кнопка «Выйти» (в шапке или на странице
 * аккаунта): по клику она открывает диалог, а не выходит сразу.
 */
const LogoutDialog = ({ children }: { children: ReactElement }) => {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const handleLogout = async () => {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await dispatch(signOut())
      navigate('/login', { replace: true })
    } catch (reason) {
      setError((reason as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="max-w-[440px]">
        <DialogTitle>Выйти из интернет-банка?</DialogTitle>
        <DialogDescription className="text-[15px] text-ink-2">
          Чтобы вернуться, понадобится снова войти по логину
        </DialogDescription>
        {error && <p role="alert">{error}</p>}
        <DialogFooter>
          <Button
            disabled={busy}
            onClick={handleLogout}
            className="h-auto px-[18px] py-3"
          >
            Выйти
          </Button>
          <DialogClose asChild>
            <Button
              variant="secondary"
              className="h-auto px-[18px] py-3 font-medium"
            >
              Отмена
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default LogoutDialog
