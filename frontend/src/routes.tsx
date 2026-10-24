import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { RequireAuth } from '@/shared/auth/RequireAuth'
import { FEATURES } from '@/shared/constants/features'
import PageLoader from '@/shared/ui/PageLoader'
import AlfaLayout from '@/widgets/Layout/AlfaLayout'
import CompanyLayout from '@/widgets/Layout/CompanyLayout'
import PulseLayout from '@/widgets/Layout/PulseLayout'

const Login = lazy(() => import('./pages/Login'))
const Home = lazy(() => import('./pages/Home'))
const PulseSummary = lazy(() => import('./pages/PulseSummary'))
const PulseSources = lazy(() => import('./pages/PulseSources'))
const Insights = lazy(() => import('./pages/Insights'))
const AnalyzeNews = lazy(() => import('./pages/AnalyzeNews'))
const InsightsHistory = lazy(() => import('./pages/InsightsHistory'))
const Insight = lazy(() => import('./pages/Insight'))
const CompanyProfile = lazy(() => import('./pages/CompanyProfile'))
const CompanyContext = lazy(() => import('./pages/CompanyContext'))
const PulseSettings = lazy(() => import('./pages/PulseSettings'))
const Account = lazy(() => import('./pages/Account'))
const ServiceStatus = lazy(() => import('./pages/ServiceStatus'))
const NotFound = lazy(() => import('./pages/NotFound'))

/**
 * Маршруты: вход без оболочки; интернет-банк — в оболочке Альфа-Бизнеса;
 * Пульс — вложенный каркас со своими вкладками; «Моя компания» — с подменю.
 */
export const AppRoutes = () => (
  <Routes>
    <Route
      path="/login"
      element={
        <Suspense fallback={<PageLoader />}>
          <Login />
        </Suspense>
      }
    />

    <Route
      element={
        <RequireAuth>
          <AlfaLayout />
        </RequireAuth>
      }
    >
      <Route index element={<Home />} />

      <Route path="pulse" element={<PulseLayout />}>
        <Route index element={<Navigate to="summary" replace />} />
        <Route path="summary" element={<PulseSummary />} />
        {FEATURES.sources && (
          <Route path="sources" element={<PulseSources />} />
        )}
        <Route path="insights" element={<Insights />} />
        <Route path="insights/new" element={<AnalyzeNews />} />
        {FEATURES.history && (
          <Route path="insights/history" element={<InsightsHistory />} />
        )}
        <Route path="insights/:insightId" element={<Insight />} />

        <Route path="company" element={<CompanyLayout />}>
          <Route index element={<Navigate to="profile" replace />} />
          <Route path="profile" element={<CompanyProfile />} />
          <Route path="context" element={<CompanyContext />} />
          <Route path="settings" element={<PulseSettings />} />
          <Route path="account" element={<Account />} />
          <Route path="status" element={<ServiceStatus />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFound />} />
    </Route>
  </Routes>
)
