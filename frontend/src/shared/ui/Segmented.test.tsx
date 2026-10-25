import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import Segmented, { type SegmentedOption } from './Segmented'

type Kind = 'all' | 'risk' | 'opp'

const OPTIONS: SegmentedOption<Kind>[] = [
  { value: 'all', label: 'Все' },
  { value: 'risk', label: 'Риски' },
  { value: 'opp', label: 'Возможности' },
]

describe('Segmented', () => {
  it('клик по сегменту переключает', () => {
    const onChange = vi.fn()
    render(
      <Segmented<Kind>
        options={OPTIONS}
        value="all"
        onChange={onChange}
        label="Тип"
      />
    )

    fireEvent.click(screen.getByRole('tab', { name: 'Риски' }))

    expect(onChange).toHaveBeenCalledWith('risk')
    expect(screen.getByRole('tab', { name: 'Все' })).toHaveAttribute(
      'aria-selected',
      'true'
    )
  })
})
