import { type PayloadAction, createSlice } from '@reduxjs/toolkit'

import { storageSave } from '@/shared/storage/storage'

import type { ICompanyProfile } from '../models/ICompany'
import { getCompanyProfile } from '../service/Company/getCompanyProfile'

const CURRENT_COMPANY_KEY = 'current_company_id'

export interface CompanyState {
  /** source_id выбранной компании — одной из компаний логина. */
  currentCompanyId: string | null
  profile: ICompanyProfile | null
  loading: boolean
  error: string | undefined
  /**
   * Последний запрос профиля. Проверки по компании мало: при A → B → A оба
   * запроса A совпадают с текущей компанией, и запоздавший первый затёр бы
   * свежий профиль или показал ошибку после успешной загрузки.
   */
  requestId: string | null
}

// Сохранённый выбор берём, только если компания доступна логину сессии.
const initialCompanyId = (): string | null => null

const initialState: CompanyState = {
  currentCompanyId: initialCompanyId(),
  profile: null,
  loading: false,
  error: undefined,
  requestId: null,
}

const companySlice = createSlice({
  name: 'company',
  initialState,
  reducers: {
    setCurrentCompany: (state, action: PayloadAction<string>) => {
      state.currentCompanyId = action.payload
      state.profile = null
      state.error = undefined
      // Запрос прежней компании больше не актуален. pending новой компании
      // придёт только после рендера (из useEffect), и ответ старого запроса
      // успел бы лечь в профиль уже выбранной компании.
      state.requestId = null
      state.loading = false
      storageSave(CURRENT_COMPANY_KEY, action.payload)
    },
  },
  extraReducers: (builder) => {
    // Свой ответ — это ответ последнего запроса и по выбранной компании.
    // Вторая проверка — страховка на случай, если requestId не сброшен.
    const isCurrent = (
      state: CompanyState,
      meta: { requestId: string; arg: string }
    ) =>
      meta.requestId === state.requestId && meta.arg === state.currentCompanyId

    builder
      .addCase(getCompanyProfile.pending, (state, action) => {
        state.requestId = action.meta.requestId
        state.loading = true
        state.error = undefined
      })
      .addCase(getCompanyProfile.fulfilled, (state, action) => {
        if (!isCurrent(state, action.meta)) return
        state.loading = false
        state.profile = action.payload
      })
      .addCase(getCompanyProfile.rejected, (state, action) => {
        if (!isCurrent(state, action.meta)) return
        state.loading = false
        state.error = action.payload ?? 'Не удалось загрузить профиль компании'
      })
  },
})

export const { setCurrentCompany } = companySlice.actions
export default companySlice.reducer
