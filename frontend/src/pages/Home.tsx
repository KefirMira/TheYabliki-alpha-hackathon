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
    <QuickActions />
    <PaymentStatuses />
    <AccountCards />
    <PulseWidget />
    <OperationsHistory />
  </>
)

export default Home
