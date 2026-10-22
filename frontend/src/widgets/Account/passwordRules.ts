/** Правила пароля из макета и оценка его надёжности. */

export interface PasswordRule {
  label: string
  ok: boolean
}

export const passwordRules = (password: string): PasswordRule[] => [
  { label: 'Не менее 8 символов', ok: password.length >= 8 },
  { label: 'Есть цифра', ok: /\d/.test(password) },
  { label: 'Есть буква', ok: /[A-Za-zА-Яа-яЁё]/.test(password) },
]

export const STRENGTH_LABELS = ['', 'Слабый', 'Средний', 'Хороший', 'Надёжный']

/** 0–4: число выполненных правил и бонус за длину 12+ со спецсимволом. */
export const passwordStrength = (password: string): number => {
  if (!password) return 0
  const passed = passwordRules(password).filter((rule) => rule.ok).length
  const bonus =
    password.length >= 12 && /[^A-Za-z0-9А-Яа-яЁё]/.test(password) ? 1 : 0
  return passed + bonus
}

export interface PasswordForm {
  current: string
  next: string
  repeat: string
}

/** Текст ошибки формы смены пароля или null, если всё верно. */
export const passwordFormError = (form: PasswordForm): string | null => {
  if (form.repeat && form.repeat !== form.next) return 'Пароли не совпадают'
  if (!form.current) return 'Введите текущий пароль'
  if (!passwordRules(form.next).every((rule) => rule.ok)) {
    return 'Новый пароль не соответствует правилам'
  }
  if (form.repeat !== form.next) return 'Повторите новый пароль'
  return null
}
