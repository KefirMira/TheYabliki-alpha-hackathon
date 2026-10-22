import { combineReducers } from '@reduxjs/toolkit'

import companyReducer from './reducers/CompanySlice'
import insightsReducer from './reducers/InsightsSlice'

export const reducer = combineReducers({
  company: companyReducer,
  insights: insightsReducer,
})
