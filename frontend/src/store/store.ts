import { configureStore } from '@reduxjs/toolkit'

import { reducer } from './rootReducer'
import { sessionScopeMiddleware } from './sessionScopeMiddleware'

export const setupStore = () =>
  configureStore({
    reducer,
    middleware: (getDefaultMiddleware) =>
      getDefaultMiddleware({
        serializableCheck: false,
      }).concat(sessionScopeMiddleware),
  })
