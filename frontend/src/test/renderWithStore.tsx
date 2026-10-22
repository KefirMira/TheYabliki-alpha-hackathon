import type { ReactElement } from 'react'
import { configureStore } from '@reduxjs/toolkit'
import { render } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter, type MemoryRouterProps } from 'react-router-dom'

import { reducer } from '@/store/rootReducer'
import type { RootState } from '@/store/types'

export const makeTestStore = (preloadedState?: Partial<RootState>) =>
  configureStore({ reducer, preloadedState })

/** Компонент со стором и роутером — для тестов страниц. */
export const renderWithStore = (
  ui: ReactElement,
  {
    store = makeTestStore(),
    initialEntries = ['/'],
  }: {
    store?: ReturnType<typeof makeTestStore>
    initialEntries?: MemoryRouterProps['initialEntries']
  } = {}
) => ({
  store,
  ...render(
    <Provider store={store}>
      <MemoryRouter
        initialEntries={initialEntries}
        // Как в App: те же флаги и без предупреждений в выводе тестов.
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        {ui}
      </MemoryRouter>
    </Provider>
  ),
})
