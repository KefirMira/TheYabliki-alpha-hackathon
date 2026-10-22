import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import PageLoader from '@/shared/ui/PageLoader'
import PulseLayout from '@/widgets/Layout/PulseLayout'

const Insights = lazy(() => import('./pages/Insights'))
const InProgress = lazy(() => import('./pages/InProgress'))
const NotFound = lazy(() => import('./pages/NotFound'))

export const AppRoutes = () => (
  <PulseLayout>
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/" element={<Navigate to="/insights" replace />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="/summary" element={<InProgress />} />
        <Route path="/company" element={<InProgress />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  </PulseLayout>
)
