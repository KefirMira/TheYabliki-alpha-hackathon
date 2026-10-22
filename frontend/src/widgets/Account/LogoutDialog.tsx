import type { ReactElement } from 'react'
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
import { logout } from '@/store/reducers/AuthSlice'

/**
 * Подтверждение выхода. children — кнопка «Выйти» (в шапке или на странице
 * аккаунта): по клику она открывает диалог, а не выходит сразу.
 */
const LogoutDialog = ({ children }: { children: ReactElement }) => {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()

  const handleLogout = () => {
    dispatch(logout())
    navigate('/login', { replace: true })
  }

  return (
    <Dialog>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="max-w-[440px]">
        <DialogTitle>Выйти из интернет-банка?</DialogTitle>
        <DialogDescription className="text-[15px] text-ink-2">
          Чтобы вернуться, понадобится снова войти по логину
        </DialogDescription>
        <DialogFooter>
          <Button onClick={handleLogout} className="h-auto px-[18px] py-3">
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
