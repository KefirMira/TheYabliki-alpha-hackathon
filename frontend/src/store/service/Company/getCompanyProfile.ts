import { createAsyncThunk } from '@reduxjs/toolkit'

import { fetchCompanyProfile } from '@/shared/api/companies.api'
import type { ICompanyProfile } from '@/store/models/ICompany'

export const getCompanyProfile = createAsyncThunk<
  ICompanyProfile,
  string,
  { rejectValue: string }
>('company/getCompanyProfile', async (companyId, { rejectWithValue }) => {
  try {
    return await fetchCompanyProfile(companyId)
  } catch (error) {
    return rejectWithValue(
      error instanceof Error
        ? error.message
        : 'Не удалось загрузить профиль компании'
    )
  }
})
