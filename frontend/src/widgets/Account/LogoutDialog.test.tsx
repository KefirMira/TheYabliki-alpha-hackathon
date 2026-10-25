import { fireEvent, screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { login } from '@/store/reducers/AuthSlice'
import { makeTestStore, renderWithStore } from '@/test/renderWithStore'

import LogoutDialog from './LogoutDialog'

const renderDialog = () => {
  const store = makeTestStore()
  store.dispatch(
    login({ user_id: 'synthetic-user', login: 'expert', companies: [] })
  )
  renderWithStore(
    <Routes>
      <Route path="/login" element={<span>Экран входа</span>} />
      <Route
        path="*"
        element={
          <LogoutDialog>
            <button type="button">Выйти</button>
          </LogoutDialog>
        }
      />
    </Routes>,
    { store }
  )
  return store
}

describe('LogoutDialog', () => {
  it('«Выйти» сначала спрашивает подтверждение', () => {
    const store = renderDialog()

    fireEvent.click(screen.getByRole('button', { name: 'Выйти' }))

    expect(
      screen.getByRole('dialog', { name: 'Выйти из интернет-банка?' })
    ).toBeInTheDocument()
    expect(store.getState().auth.isAuthenticated).toBe(true)
  })

  it('«Отмена» оставляет в банке', () => {
    const store = renderDialog()

    fireEvent.click(screen.getByRole('button', { name: 'Выйти' }))
    fireEvent.click(screen.getByRole('button', { name: 'Отмена' }))

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(store.getState().auth.isAuthenticated).toBe(true)
  })

  it('подтверждение выходит на экран входа', async () => {
    const store = renderDialog()

    fireEvent.click(screen.getByRole('button', { name: 'Выйти' }))
    const dialog = screen.getByRole('dialog')
    fireEvent.click(
      Array.from(dialog.querySelectorAll('button')).find(
        (button) => button.textContent === 'Выйти'
      )!
    )

    await screen.findByText('Экран входа')
    expect(store.getState().auth.isAuthenticated).toBe(false)
    expect(screen.getByText('Экран входа')).toBeInTheDocument()
  })
})
