import { fireEvent, screen } from '@testing-library/react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { renderWithStore } from '@/test/renderWithStore'

import Login from './Login'

const Where = () => {
  const { pathname, search, hash } = useLocation()
  return <span data-testid="where">{pathname + search + hash}</span>
}

describe('Login', () => {
  it('после входа возвращает на исходный адрес вместе с фильтрами', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ access_token: 'synthetic-token' }))
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              user_id: 'synthetic-user',
              login: 'expert',
              companies: [],
            })
          )
        )
    )
    const from = {
      pathname: '/pulse/insights',
      search: '?type=risk&fav=1',
      hash: '#top',
    }
    renderWithStore(
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Where />} />
      </Routes>,
      { initialEntries: [{ pathname: '/login', state: { from } }] }
    )

    fireEvent.change(screen.getByLabelText('Логин'), {
      target: { value: 'expert' },
    })
    fireEvent.change(screen.getByLabelText('Пароль'), {
      target: { value: 'synthetic-password' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Войти' }))

    expect(await screen.findByTestId('where')).toHaveTextContent(
      '/pulse/insights?type=risk&fav=1#top'
    )
  })
})
