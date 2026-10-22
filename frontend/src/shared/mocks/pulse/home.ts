/** Демо-данные главной Альфа-Бизнеса — оболочка банка вокруг Пульса. */

export const HOME_ACCOUNTS = [
  {
    title: 'Расчётный счёт',
    amount: '184 562 300',
    cents: ',48 ₽',
    note: '40702 810 4 0000 0123456',
  },
  {
    title: 'Кредитная линия',
    amount: '1,2 млрд',
    cents: ' ₽',
    note: 'Выбрано 64% · ставка КС + 2,1%',
  },
]

export const PAYMENT_STATUSES = [
  { label: 'Подписать', count: 3, accent: true },
  { label: 'Доработать', count: 1 },
  { label: 'Черновики', count: 2 },
  { label: 'Отклонённые', count: 0, muted: true },
]

export const BANK_IN_WORK = 4

export const OPERATIONS = [
  {
    date: '15.09',
    counterparty: 'ООО «УралСтройПуть»',
    amount: '+4 820 000,00 ₽',
    income: true,
  },
  {
    date: '15.09',
    counterparty: 'ООО «Волга-Нефтепродукт»',
    amount: '−1 312 400,00 ₽',
  },
]

export const PULSE_TEASER =
  'Сегодня важно: ставка 14% сохранится — кредит и лизинг не подешевеют до 2027 г.'

/** Уведомления в колокольчике. */
export const BELL_PAYMENT = {
  title: 'Платёж №214 ждёт подписи',
  amount: '1 240 000 ₽',
  time: 'Вчера, 18:42',
}
