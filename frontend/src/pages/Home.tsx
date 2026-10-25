import {
  AccountCards,
  OperationsHistory,
  PaymentStatuses,
  QuickActions,
} from '@/widgets/Home/BankOverview'
import PulseWidget from '@/widgets/Home/PulseWidget'

/** Главная Альфа-Бизнеса: сначала банк, затем тизер Пульса в первом экране. */
const Home = () => (
  <>
    <p role="note" className="rounded-xl bg-white p-3 text-sm text-ink-3">
      Банковская витрина: остатки и операции ниже вымышлены и не относятся к
      выбранной компании. Профиль и инсайты загружаются с сервера.
    </p>
    <QuickActions />
    <PaymentStatuses />
    <AccountCards />
    <PulseWidget />
    <OperationsHistory />
  </>
)

export default Home
