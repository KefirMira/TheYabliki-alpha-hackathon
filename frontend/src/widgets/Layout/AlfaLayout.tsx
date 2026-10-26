import { isSavedPilotCompany } from '@/shared/constants/savedPilot'
import { useAppSelector } from '@/store/hooks/redux'
import { Suspense } from 'react'
import { Outlet } from 'react-router-dom'

import { useFeedPolling } from '@/hooks/useFeedPolling'
import { usePulseData } from '@/hooks/usePulseData'
import PageLoader from '@/shared/ui/PageLoader'

import AlfaHeader from './AlfaHeader'
import AlfaSidebar from './AlfaSidebar'
import ServiceStatusBanner from './ServiceStatusBanner'

/**
 * Оболочка интернет-банка Альфа-Бизнес: меню слева, шапка, контент. Всё,
 * кроме Пульса, — витрина: приглушено и по клику объясняет, что не работает.
 */
const AlfaLayout = () => {
  const pilot = useAppSelector(
    (state) => isSavedPilotCompany(state.company.currentCompanyId)
  )
  usePulseData()
  useFeedPolling()

  return (
    <div className="grid min-h-screen grid-cols-1 bg-surface-page lg:grid-cols-[264px_minmax(0,1fr)]">
      <AlfaSidebar />
      <div className="flex min-w-0 flex-col">
        <AlfaHeader />
        <main className="flex min-w-0 flex-1 flex-col gap-4 px-4 pb-10 pt-1 lg:px-10">
          <ServiceStatusBanner />
          {pilot && (
            <p role="note" className="rounded-xl bg-white p-3 text-sm">
              Синтетический пример · сохранённый LLM-пилот. Финансовая
              достоверность не подтверждена. Даты записей в ленте относятся к
              импорту; новый анализ не запускался.
            </p>
          )}
          <Suspense fallback={<PageLoader />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  )
}

export default AlfaLayout
