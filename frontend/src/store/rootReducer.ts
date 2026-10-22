import { combineReducers } from '@reduxjs/toolkit'

import analysisReducer from './reducers/AnalysisSlice'
import authReducer from './reducers/AuthSlice'
import companyReducer from './reducers/CompanySlice'
import insightsReducer from './reducers/InsightsSlice'
import pulseReducer from './reducers/PulseSlice'

export const reducer = combineReducers({
  auth: authReducer,
  // company и insights — данные из API бэкенда; экраны пока на демо-данных
  // (pulse), слайсы ждут подключения.
  company: companyReducer,
  insights: insightsReducer,
  pulse: pulseReducer,
  analysis: analysisReducer,
})
