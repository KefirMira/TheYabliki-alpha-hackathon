import { describe, expect, it } from 'vitest'

import { plural } from './plural'

const forms: [string, string, string] = ['инсайт', 'инсайта', 'инсайтов']

describe('plural', () => {
  it.each([
    [1, '1 инсайт'],
    [2, '2 инсайта'],
    [5, '5 инсайтов'],
    [11, '11 инсайтов'],
    [12, '12 инсайтов'],
    [21, '21 инсайт'],
    [22, '22 инсайта'],
    [111, '111 инсайтов'],
  ])('%i → %s', (count, expected) => {
    expect(plural(count, forms)).toBe(expected)
  })
})
