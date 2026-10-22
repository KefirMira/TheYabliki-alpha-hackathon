import { describe, expect, it } from 'vitest'

import { passwordFormError, passwordStrength } from './passwordRules'

describe('passwordStrength', () => {
  it('пустой пароль — 0', () => {
    expect(passwordStrength('')).toBe(0)
  })

  it('все три правила — «Хороший», длинный со спецсимволом — «Надёжный»', () => {
    expect(passwordStrength('abcdefg1')).toBe(3)
    expect(passwordStrength('abcdefgh1234!')).toBe(4)
  })
})

describe('passwordFormError', () => {
  it('несовпадение повтора видно сразу', () => {
    expect(
      passwordFormError({ current: '', next: 'abcdefg1', repeat: 'abc' })
    ).toBe('Пароли не совпадают')
  })

  it('нет текущего пароля', () => {
    expect(
      passwordFormError({ current: '', next: 'abcdefg1', repeat: 'abcdefg1' })
    ).toBe('Введите текущий пароль')
  })

  it('новый пароль без цифры не проходит', () => {
    expect(
      passwordFormError({ current: 'old', next: 'abcdefgh', repeat: '' })
    ).toBe('Новый пароль не соответствует правилам')
  })

  it('верная форма — без ошибки', () => {
    expect(
      passwordFormError({
        current: 'old',
        next: 'abcdefg1',
        repeat: 'abcdefg1',
      })
    ).toBeNull()
  })
})
