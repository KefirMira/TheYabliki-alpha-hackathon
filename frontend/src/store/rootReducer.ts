import { combineReducers, type UnknownAction } from '@reduxjs/toolkit'

import analysisReducer from './reducers/AnalysisSlice'
import authReducer from './reducers/AuthSlice'
import companyReducer from './reducers/CompanySlice'
import insightsReducer from './reducers/InsightsSlice'
import pulseReducer from './reducers/PulseSlice'

const combined = combineReducers({
  auth: authReducer,
  // Private API data is reset on every actor transition.
  company: companyReducer,
  insights: insightsReducer,
  pulse: pulseReducer,
  analysis: analysisReducer,
})

type State = ReturnType<typeof combined>
export const reducer = (
  state: State | undefined,
  action: UnknownAction
): State => {
  if (action.type === 'auth/login' || action.type === 'auth/logout') {
    const empty = combined(undefined, { type: '@@session-reset' })
    state = {
      ...empty,
      auth: state?.auth ?? empty.auth,
      pulse: state?.pulse ?? empty.pulse,
    }
  }
  return combined(state, action)
}
