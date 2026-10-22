import { Suspense } from 'react'
import { Outlet } from 'react-router-dom'

import { usePulseData } from '@/hooks/usePulseData'
import PageLoader from '@/shared/ui/PageLoader'

import AlfaHeader from './AlfaHeader'
import AlfaSidebar from './AlfaSidebar'

/** Оболочка интернет-банка Альфа-Бизнес: меню слева, шапка, контент. */
const AlfaLayout = () => {
  usePulseData()

  return (
    <div className="grid min-h-screen grid-cols-1 bg-surface-page lg:grid-cols-[264px_minmax(0,1fr)]">
      <AlfaSidebar />
      <div className="flex min-w-0 flex-col">
        <AlfaHeader />
        <main className="flex min-w-0 flex-1 flex-col gap-4 px-4 pb-10 pt-1 lg:px-10">
          <Suspense fallback={<PageLoader />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  )
}

export default AlfaLayout
