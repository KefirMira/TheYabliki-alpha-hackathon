import { describe, expect, it } from 'vitest'

import type { ICompanyProfile } from '@/store/models/ICompany'

import {
  companyNameOf,
  companyProfileFields,
  formatRevenue,
} from './companyMappers'

const profile = (patch: Partial<ICompanyProfile> = {}): ICompanyProfile => ({
  company_id: 'DEMO-001',
  name: 'Пекарня',
  name_is_placeholder: false,
  industry: 'Хлебопечение',
  region: 'Москва',
  revenue: '125000000.00',
  revenue_year: 2025,
  client_status: 'CLIENT',
  credit_exposure: null,
  ...patch,
})

describe('formatRevenue', () => {
  it('группирует разряды и убирает нулевые копейки', () => {
    expect(formatRevenue('125000000.00')).toBe(
      '125\u00A0000\u00A0000 (единицы и валюта не указаны)'
    )
  })

  it('сохраняет ненулевые копейки без потери точности', () => {
    expect(formatRevenue('90071992547409931.5')).toBe(
      '90\u00A0071\u00A0992\u00A0547\u00A0409\u00A0931,5 (единицы и валюта не указаны)'
    )
  })

  it('нечисловую строку возвращает как есть', () => {
    expect(formatRevenue('n/a')).toBe('n/a')
  })
})

describe('companyProfileFields', () => {
  it('берёт поля из API с годом выручки', () => {
    expect(companyProfileFields(profile())).toEqual([
      { key: 'industry', label: 'Отрасль', value: 'Хлебопечение' },
      { key: 'region', label: 'Регион', value: 'Москва' },
      {
        key: 'revenue',
        label: 'Выручка за 2025 год',
        value: '125\u00A0000\u00A0000 (единицы и валюта не указаны)',
      },
      { key: 'client_status', label: 'Статус', value: 'Клиент банка' },
    ])
  })

  it('пустые поля не показывает', () => {
    const fields = companyProfileFields(
      profile({
        industry: null,
        revenue: null,
        revenue_year: null,
        client_status: null,
      })
    )
    expect(fields.map((field) => field.key)).toEqual(['region'])
  })
})

describe('companyNameOf', () => {
  it('без названия возвращает идентификатор', () => {
    expect(
      companyNameOf(profile({ name: null, name_is_placeholder: true }))
    ).toBe('DEMO-001')
  })
})
