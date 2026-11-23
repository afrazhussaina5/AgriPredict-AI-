import React, { Suspense } from 'react'
import { AuthProvider } from './auth/AuthProvider'
import { AppShell } from './components/AppShell'
import { I18nProvider } from './i18n/I18nProvider'
import { ToastProvider } from './components/Toast'
import { FloatingVoiceAssistant } from './components/FloatingVoiceAssistant'
import { LocationProvider } from './context/LocationContext'
import { LoadingState } from './components/states'
import { useRoute } from './router'

// Code-split pages with dynamic imports for fast initial rural mobile loads
const LandingPage = React.lazy(() => import('./pages/LandingPage').then(m => ({ default: m.LandingPage })))
const AuthPage = React.lazy(() => import('./pages/AuthPage').then(m => ({ default: m.AuthPage })))
const DashboardPage = React.lazy(() => import('./pages/DashboardPage').then(m => ({ default: m.DashboardPage })))
const MarketPage = React.lazy(() => import('./pages/MarketPage').then(m => ({ default: m.MarketPage })))
const ForecastDashboardPage = React.lazy(() => import('./pages/ForecastDashboardPage').then(m => ({ default: m.ForecastDashboardPage })))
const MandiComparisonPage = React.lazy(() => import('./pages/MandiComparisonPage').then(m => ({ default: m.MandiComparisonPage })))
const AgriMitraChatPage = React.lazy(() => import('./pages/AgriMitraChatPage').then(m => ({ default: m.AgriMitraChatPage })))
const GovernmentSchemesPage = React.lazy(() => import('./pages/GovernmentSchemesPage').then(m => ({ default: m.GovernmentSchemesPage })))
const BuyerMarketplacePage = React.lazy(() => import('./pages/BuyerMarketplacePage').then(m => ({ default: m.BuyerMarketplacePage })))
const ServicesPage = React.lazy(() => import('./pages/ServicesPage').then(m => ({ default: m.ServicesPage })))
const LotsPage = React.lazy(() => import('./pages/LotsPage').then(m => ({ default: m.LotsPage })))
const FarmerProfilePage = React.lazy(() => import('./pages/FarmerProfilePage').then(m => ({ default: m.FarmerProfilePage })))
const ReferencePage = React.lazy(() => import('./pages/ReferencePage').then(m => ({ default: m.ReferencePage })))
const CropAnalysisPage = React.lazy(() => import('./pages/CropAnalysisPage').then(m => ({ default: m.CropAnalysisPage })))
const NotFoundPage = React.lazy(() => import('./pages/NotFoundPage').then(m => ({ default: m.NotFoundPage })))

function CurrentRoute() {
  const path = useRoute()

  return (
    <Suspense fallback={<LoadingState />}>
      {(() => {
        if (path === '/') return <LandingPage />
        if (path === '/signin') return <AuthPage />
        if (path === '/analyze') return <CropAnalysisPage />
        if (path === '/reference') return <ReferencePage />
        if (path === '/market') return <MarketPage />
        if (path === '/forecast') return <ForecastDashboardPage />
        if (path === '/chat') return <AgriMitraChatPage />
        if (path === '/compare') return <MandiComparisonPage />
        if (path === '/schemes') return <GovernmentSchemesPage />
        if (path === '/buyers' || path.startsWith('/buyers/')) return <BuyerMarketplacePage />
        if (path === '/services' || path.startsWith('/services/')) return <ServicesPage />
        if (path === '/lots') return <LotsPage />
        if (path === '/profile') return <FarmerProfilePage />
        if (path === '/dashboard' || path.startsWith('/dashboard/')) {
          return <DashboardPage path={path} />
        }
        return <NotFoundPage />
      })()}
    </Suspense>
  )
}

export default function App() {
  return (
    <I18nProvider>
      <AuthProvider>
        <LocationProvider>
          <ToastProvider>
            <AppShell>
              <CurrentRoute />
              <FloatingVoiceAssistant />
            </AppShell>
          </ToastProvider>
        </LocationProvider>
      </AuthProvider>
    </I18nProvider>
  )
}
