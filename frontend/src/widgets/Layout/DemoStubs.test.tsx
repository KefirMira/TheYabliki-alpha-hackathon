import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Toaster } from '@/components/ui/toaster'
import { renderWithStore } from '@/test/renderWithStore'

import AlfaSidebar from './AlfaSidebar'

const renderSidebar = () =>
  renderWithStore(
    <>
      <AlfaSidebar />
      <Toaster />
    </>
  )

describe('нерабочие разделы банка', () => {
  it('клик по разделу вне прототипа объясняет, что он не работает', () => {
    renderSidebar()

    const payments = screen.getByRole('button', {
      name: 'Платежи — в прототипе не работает',
    })
    expect(payments).toHaveAttribute('aria-disabled', 'true')

    fireEvent.click(payments)

    expect(screen.getByText(/эта часть интернет-банка/)).toHaveTextContent(
      '«Платежи» — эта часть интернет-банка в прототипе не работает'
    )
  })

  it('рабочие разделы остаются ссылками', () => {
    renderSidebar()

    expect(screen.getByRole('link', { name: /Пульс бизнеса/ })).toHaveAttribute(
      'href',
      '/pulse/summary'
    )
    expect(screen.getByRole('link', { name: 'Главная' })).toHaveAttribute(
      'href',
      '/'
    )
  })
})
