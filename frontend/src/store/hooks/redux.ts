import type { TypedUseSelectorHook } from 'react-redux'
import { useDispatch } from 'react-redux'
import { useSelector } from 'react-redux'

import type { AppDispatch, RootState } from '../types'

export const useAppDispatch = () => useDispatch<AppDispatch>()
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector
