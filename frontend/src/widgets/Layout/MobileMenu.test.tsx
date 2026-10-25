import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderWithStore } from '@/test/renderWithStore'

import MobileMenu from './MobileMenu'

describe('MobileMenu', () => {
  it('открывает меню банка с аккаунтом и выходом', () => {
    renderWithStore(<MobileMenu />)

    fireEvent.click(screen.getByRole('button', { name: 'Меню' }))

    const menu = screen.getByRole('dialog', { name: 'Меню интернет-банка' })
    expect(menu).toHaveTextContent('Пульс бизнеса')
    expect(
      screen.getByRole('link', { name: 'Аккаунт и безопасность' })
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Выйти' })).toBeInTheDocument()
  })

  it('переход по пункту закрывает меню', () => {
    renderWithStore(<MobileMenu />)

    fireEvent.click(screen.getByRole('button', { name: 'Меню' }))
    fireEvent.click(screen.getByRole('link', { name: /Пульс бизнеса/ }))

    expect(screen.queryByRole('dialog')).toBeNull()
  })
})
