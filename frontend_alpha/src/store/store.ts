import { configureStore } from '@reduxjs/toolkit'

import { reducer } from './rootReducer'

export const setupStore = () =>
  configureStore({
    reducer,
    middleware: (getDefaultMiddleware) =>
      getDefaultMiddleware({
        serializableCheck: false,
      }),
  })
