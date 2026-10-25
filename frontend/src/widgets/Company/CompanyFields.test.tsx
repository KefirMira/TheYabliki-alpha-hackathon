import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import CompanyFields from './CompanyFields'
describe('company profile attribution', () => {
  it('does not invent bank provenance or revenue currency', () => {
    render(
      <CompanyFields
        profile={{
          company_id: 'DEMO-001',
          name: null,
          name_is_placeholder: true,
          industry: 'Синтетическая отрасль',
          region: null,
          revenue: '12.34',
          revenue_year: null,
          client_status: null,
          credit_exposure: null,
        }}
      />
    )
    expect(screen.queryByText('По данным банка')).not.toBeInTheDocument()
    expect(
      screen.getAllByText('Из сохранённого профиля; источник не подтверждён')
    ).toHaveLength(2)
    expect(screen.getByText(/единицы и валюта не указаны/)).toBeInTheDocument()
  })
})
