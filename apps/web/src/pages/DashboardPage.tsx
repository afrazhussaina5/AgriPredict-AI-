import { useCallback, useEffect, useState } from 'react'

import {
  ApiError,
  fetchFarmerProfile,
  fetchMarketPrices,
  fetchMyLots,
  fetchReferenceStatus,
  type LotStatus,
} from '../api/client'
import { useAuth } from '../auth/context'
import { RoleSwitcherBar } from '../components/RoleSwitcherBar'
import { WeatherWidget } from '../components/WeatherWidget'
import { EmptyState, ErrorState, LoadingState } from '../components/states'
import { Badge, Button, Card } from '../components/ui'
import { useToast } from '../components/Toast'
import { useTranslation } from '../i18n/useTranslation'
import { navigate } from '../router'
import { isDashboardRole, type DashboardRole } from '../roles'
import { useLocationContext } from '../context/LocationContext'

type Loadable<T> =
  | { status: 'loading' }
  | { status: 'ready'; data: T }
  | { status: 'error'; code?: string }

const LOADING: Loadable<never> = { status: 'loading' }

const EMPTY_COUNTS: Record<LotStatus, number> = {
  draft: 0,
  published: 0,
  paused: 0,
  closed: 0,
  archived: 0,
}

const STATUS_KEY = {
  draft: 'lot.statusDraft',
  published: 'lot.statusPublished',
  paused: 'lot.statusPaused',
  closed: 'lot.statusClosed',
  archived: 'lot.statusArchived',
} as const

const STATUS_TONE = {
  draft: 'neutral',
  published: 'success',
  paused: 'warning',
  closed: 'info',
  archived: 'neutral',
} as const

const ROLE_TO_DASHBOARD: Record<string, DashboardRole> = {
  farmer: 'farmer',
  buyer: 'buyer',
  transport_provider: 'transport',
  storage_provider: 'storage',
  admin: 'admin',
}

const MARKET_PREVIEW_ROWS = 5
const LOT_PREVIEW_ROWS = 5

function usePanel<T>(loader: () => Promise<T>): { state: Loadable<T>; retry: () => void } {
  const [state, setState] = useState<Loadable<T>>(LOADING)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    setState(LOADING)
    loader()
      .then((data) => {
        if (!cancelled) setState({ status: 'ready', data })
      })
      .catch((error: unknown) => {
        if (cancelled) return
        const code = error instanceof ApiError ? error.code : undefined
        setState({ status: 'error', code })
      })
    return () => {
      cancelled = true
    }
  }, [loader, attempt])

  const retry = useCallback(() => setAttempt((value) => value + 1), [])

  return { state, retry }
}

function PanelError({ retry }: { retry: () => void }) {
  const { t } = useTranslation()
  return (
    <ErrorState
      title={t('dash.error.title')}
      body={t('dash.error.body')}
      onRetry={retry}
    />
  )
}

/* ============================================================
   PANELS
   ============================================================ */

function ProfilePanel() {
  const { t } = useTranslation()
  const loader = useCallback(() => fetchFarmerProfile(), [])
  const { state, retry } = usePanel(loader)

  const missingProfile = state.status === 'error' && state.code === 'not_found'

  return (
    <Card title={t('dash.profile.title')}>
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && !missingProfile && <PanelError retry={retry} />}

      {missingProfile && (
        <>
          <p>{t('dash.profile.missing')}</p>
          <p>
            <Button onClick={() => navigate('/profile')}>{t('dash.profile.action')}</Button>
          </p>
        </>
      )}

      {state.status === 'ready' && (
        <>
          <p>
            <strong>
              {state.data.completion_percent === 100
                ? t('dash.profile.done')
                : t('dash.profile.complete', { percent: state.data.completion_percent })}
            </strong>
          </p>
          <p className="muted">
            {[state.data.state_name, state.data.district_name, state.data.mandi_name]
              .filter((part): part is string => Boolean(part))
              .join(' · ') || t('lot.notStated')}
          </p>
          <p>
            <Button variant="secondary" onClick={() => navigate('/profile')}>
              {t('dash.profile.action')}
            </Button>
          </p>
        </>
      )}
    </Card>
  )
}

function LotsPanel() {
  const { t } = useTranslation()
  const loader = useCallback(async () => (await fetchMyLots({ limit: 100 })).items, [])
  const { state, retry } = usePanel(loader)

  const lots = state.status === 'ready' ? state.data : []

  const counts = lots.reduce<Record<LotStatus, number>>(
    (acc, lot) => {
      acc[lot.status] += 1
      return acc
    },
    { ...EMPTY_COUNTS },
  )

  const recent = [...lots].sort((a, b) => b.id - a.id).slice(0, LOT_PREVIEW_ROWS)

  return (
    <Card
      title={t('dash.lots.title')}
      badge={lots.length > 0 ? <Badge tone={counts.published > 0 ? 'success' : 'neutral'}>{lots.length}</Badge> : undefined}
    >
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <PanelError retry={retry} />}

      {state.status === 'ready' &&
        (lots.length === 0 ? (
          <EmptyState
            title={t('dash.lots.none')}
            body={t('dash.lots.createHint')}
            action={
              <Button onClick={() => navigate('/lots')}>
                {t('dash.lots.create')}
              </Button>
            }
          />
        ) : (
          <>
            <p className="muted" style={{ margin: '0 0 var(--space-3)' }}>
              {Object.entries(counts)
                .filter(([, count]) => count > 0)
                .map(([status, count]) => (
                  <Badge key={status} tone={STATUS_TONE[status as LotStatus]}>
                    {t(STATUS_KEY[status as LotStatus])}: {count}
                  </Badge>
                ))}
            </p>

            <ul className="plain-list">
              {recent.map((lot) => (
                <li key={lot.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-1) 0' }}>
                  <span>
                    <strong>{lot.commodity_name ?? t('common.none')}</strong> ·{' '}
                    <span className="num">{lot.quantity}</span>
                  </span>
                  <Badge tone={STATUS_TONE[lot.status]}>{t(STATUS_KEY[lot.status])}</Badge>
                </li>
              ))}
            </ul>

            <div className="inline-actions" style={{ marginTop: 'var(--space-3)' }}>
              <Button variant="secondary" onClick={() => navigate('/lots')}>
                {t('dash.lots.viewAll')}
              </Button>
            </div>
          </>
        ))}
    </Card>
  )
}

function MarketPanel() {
  const { t } = useTranslation()
  const loader = useCallback(
    async () => (await fetchMarketPrices()).slice(0, MARKET_PREVIEW_ROWS),
    [],
  )
  const { state, retry } = usePanel(loader)

  return (
    <Card title={t('dash.market.title')}>
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <PanelError retry={retry} />}

      {state.status === 'ready' &&
        (state.data.length === 0 ? (
          <EmptyState
            title={t('market.empty.title')}
            body={t('market.empty.body')}
            action={
              <Button variant="secondary" onClick={() => navigate('/market')}>
                {t('dash.market.viewAll')}
              </Button>
            }
          />
        ) : (
          <>
            <ul className="plain-list">
              {state.data.map((row) => (
                <li key={`${row.mandi_code}-${row.commodity_code}`} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-2) 0', borderBottom: '1px solid var(--color-border-subtle)' }}>
                  <div>
                    <strong>{row.commodity_name}</strong>
                    <div className="text-caption muted">
                      {row.mandi_name} · {row.market_date}
                    </div>
                  </div>
                  <div className="metric-group" style={{ textAlign: 'end' }}>
                    <span className="num text-strong">₹{row.modal_price ?? t('market.noPrice')}</span>
                    <span className="text-caption muted">/ {row.unit_code}</span>
                  </div>
                </li>
              ))}
            </ul>

            <div className="inline-actions" style={{ marginTop: 'var(--space-3)' }}>
              <Button variant="secondary" onClick={() => navigate('/market')}>
                {t('dash.market.viewAll')}
              </Button>
            </div>
          </>
        ))}
    </Card>
  )
}

function ReferencePanel() {
  const { t } = useTranslation()
  const loader = useCallback(() => fetchReferenceStatus(), [])
  const { state, retry } = usePanel(loader)

  return (
    <Card title={t('dash.reference.title')}>
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <PanelError retry={retry} />}

      {state.status === 'ready' &&
        (state.data.is_populated ? (
          <>
            <p className="text-sm">
              {t('dash.reference.counts', {
                states: state.data.counts.states,
                districts: state.data.counts.districts,
                mandis: state.data.counts.mandis,
                commodities: state.data.counts.commodities,
              })}
            </p>
            <p className="text-caption muted">
              Verified administrative boundaries &amp; APMC commodity definitions.
            </p>
          </>
        ) : (
          <EmptyState title={t('dash.reference.empty')} body={state.data.note} />
        ))}

      <div className="inline-actions" style={{ marginTop: 'var(--space-3)' }}>
        <Button variant="secondary" onClick={() => navigate('/reference')}>
          {t('dash.reference.action')}
        </Button>
      </div>
    </Card>
  )
}

/* ============================================================
   1. FARMER DASHBOARD (किसान कार्यक्षेत्र)
   ============================================================ */

function FarmerDashboard({ name }: { name: string | null }) {
  const { t } = useTranslation()
  const { activeHub } = useLocationContext()

  return (
    <div className="stack anim-fade-in">
      <RoleSwitcherBar activeRole="farmer" />

      {/* Header & Welcome */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{ fontSize: '26px' }}>👨‍🌾</span>
            <h1 style={{ margin: 0 }}>{name ? t('dash.welcome', { name }) : 'Farmer Intelligence Workspace'}</h1>
          </div>
          <p className="lede" style={{ margin: '4px 0 0' }}>
            Decision-support for harvest sale timing in <strong>{activeHub.name}</strong> ({activeHub.primaryMandi}), Store vs. Sell forecast, and net take-home realization.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <Badge tone="success" className="badge--pulse">
            <span className="pulse-dot" /> APMC Live Feed Active
          </Badge>
          <Badge tone="gold">Farmer Role (किसान)</Badge>
        </div>
      </div>

      {/* Live Agricultural Weather Component */}
      <WeatherWidget />

      {/* Primary ML Action Signal Banner: STORE vs SELL */}
      <div
        style={{
          background: 'linear-gradient(135deg, #153F35 0%, #26745A 100%)',
          color: '#FFFFFF',
          borderRadius: 'var(--radius-xl)',
          padding: 'var(--space-5) var(--space-6)',
          boxShadow: 'var(--shadow-md)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 'var(--space-4)',
        }}
      >
        <div style={{ maxWidth: '36rem' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-1)' }}>
            <span
              style={{
                background: '#E9B949',
                color: '#153F35',
                fontSize: '11px',
                fontWeight: 800,
                padding: '2px 8px',
                borderRadius: 'var(--radius-pill)',
                textTransform: 'uppercase',
              }}
            >
              AI ACTION SIGNAL: STORE IN COLD STORAGE (स्टोर करें)
            </span>
            <span style={{ fontSize: '11px', opacity: 0.9 }}>10-Day Projected Gain: +8.5%</span>
          </div>
          <h2 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 800, margin: 'var(--space-1) 0', color: '#FFFFFF' }}>
            {activeHub.dominantCrop} Prices in {activeHub.district} Expected to Surge ₹380/qtl in Next 10 Days
          </h2>
          <p style={{ margin: 0, fontSize: 'var(--font-size-sm)', opacity: 0.9, lineHeight: 1.5 }}>
            Holding in warehouse costs approx ₹27/qtl for 15 days, leaving you with <strong>+₹353/quintal extra net profit</strong> compared to selling today.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
          <Button
            variant="gold"
            onClick={() => navigate('/services')}
            style={{ fontWeight: 700 }}
          >
            🏭 Find Cold Storage →
          </Button>
          <Button
            variant="secondary"
            onClick={() => navigate('/forecast')}
            style={{ background: 'rgba(255,255,255,0.2)', color: '#FFFFFF', borderColor: 'rgba(255,255,255,0.4)' }}
          >
            📈 View 10-Day ML Curve
          </Button>
        </div>
      </div>

      {/* 5 Discovery Pillars */}
      <div className="card-grid">
        {/* Pillar 1: 10-Day Forecast */}
        <div
          className="card card--interactive"
          style={{ borderColor: 'var(--color-brand)' }}
          onClick={() => navigate('/forecast')}
          role="button"
          tabIndex={0}
        >
          <span className="badge badge--success badge--pulse" style={{ marginBottom: 'var(--space-1)' }}>
            <span className="pulse-dot" /> Core Machine Learning
          </span>
          <h3 style={{ margin: 'var(--space-1) 0 var(--space-2)' }}>📈 10-Day Price Forecast</h3>
          <p className="text-body-sm muted">
            See forward price projection curves with statistical confidence bands to time your selling window.
          </p>
          <span className="btn btn--primary btn--sm" style={{ marginTop: 'var(--space-3)' }}>
            Open Forecast Engine →
          </span>
        </div>

        {/* Pillar 2: Mandi Comparison & Net Realization */}
        <div
          className="card card--interactive"
          onClick={() => navigate('/compare')}
          role="button"
          tabIndex={0}
        >
          <span className="eyebrow">Net Realization</span>
          <h3 style={{ margin: 'var(--space-1) 0 var(--space-2)' }}>⚖️ {t('nav.compare')}</h3>
          <p className="text-body-sm muted">
            Deduct diesel freight, APMC cess, and manual loading to find which nearby market yields the highest take-home cash.
          </p>
          <span className="btn btn--secondary btn--sm" style={{ marginTop: 'var(--space-3)' }}>
            Calculate Net Return →
          </span>
        </div>

        {/* Pillar 3: Government Schemes */}
        <div
          className="card card--interactive"
          onClick={() => navigate('/schemes')}
          role="button"
          tabIndex={0}
        >
          <span className="eyebrow">Government Subsidies</span>
          <h3 style={{ margin: 'var(--space-1) 0 var(--space-2)' }}>🏛️ {t('nav.schemes')}</h3>
          <p className="text-body-sm muted">
            PM-Kisan (₹6,000/yr), PMFBY crop insurance, AIF infrastructure subvention, and farm implement subsidies.
          </p>
          <span className="btn btn--secondary btn--sm" style={{ marginTop: 'var(--space-3)' }}>
            Check Eligibility →
          </span>
        </div>

        {/* Pillar 4: Commercial Buyers */}
        <div
          className="card card--interactive"
          onClick={() => navigate('/buyers')}
          role="button"
          tabIndex={0}
        >
          <span className="eyebrow">Direct Procurement</span>
          <h3 style={{ margin: 'var(--space-1) 0 var(--space-2)' }}>🤝 {t('nav.buyers')}</h3>
          <p className="text-body-sm muted">
            Browse corporate buyers &amp; FPOs with committed procurement prices, farmgate pickup, and bank NEFT terms.
          </p>
          <span className="btn btn--secondary btn--sm" style={{ marginTop: 'var(--space-3)' }}>
            View Buyer Demands →
          </span>
        </div>

        {/* Pillar 5: Transport & Storage */}
        <div
          className="card card--interactive"
          onClick={() => navigate('/services')}
          role="button"
          tabIndex={0}
        >
          <span className="eyebrow">Logistics &amp; Storage</span>
          <h3 style={{ margin: 'var(--space-1) 0 var(--space-2)' }}>🚚 {t('nav.services')}</h3>
          <p className="text-body-sm muted">
            Book local mini-trucks (Tata Ace, Eicher) or reserve space in WDRA-accredited dry and cold godowns.
          </p>
          <span className="btn btn--secondary btn--sm" style={{ marginTop: 'var(--space-3)' }}>
            Explore Services →
          </span>
        </div>
      </div>

      {/* Voluntary Optional Selling Banner */}
      <div
        className="card card--accent anim-slide-up"
        style={{
          background: 'var(--color-surface-alt)',
          borderLeft: '4px solid var(--color-brand)',
        }}
      >
        <div className="card__header">
          <div>
            <h3 style={{ margin: 0 }}>🌾 Have Harvest Ready to Sell? (100% Voluntary Choice)</h3>
            <p className="text-body-sm" style={{ margin: 'var(--space-1) 0 0' }}>
              Selling on AgriPredict AI is completely optional. You can check prices, compare mandis, and use the AI assistant without ever creating a listing. When ready to sell, publish in 2 minutes.
            </p>
          </div>
          <div className="inline-actions" style={{ flexShrink: 0 }}>
            <Button variant="primary" onClick={() => navigate('/lots')}>
              + Sell Produce
            </Button>
            <Button variant="secondary" onClick={() => navigate('/lots')}>
              My Listings
            </Button>
          </div>
        </div>
      </div>

      {/* Live Data Panels */}
      <div className="card-grid">
        <MarketPanel />
        <LotsPanel />
      </div>

      <div className="card-grid">
        <ProfilePanel />
        <ReferencePanel />
      </div>
    </div>
  )
}

/* ============================================================
   2. TRANSPORTER DASHBOARD (ट्रांसपोर्टर कार्यक्षेत्र)
   ============================================================ */

type TransporterVehicle = {
  id: string
  model: string
  capacityTons: number
  capacityBags: number
  ratePerKm: number
  status: 'available' | 'on_route' | 'maintenance'
  location: string
}

function TransportDashboard() {
  const { activeHub } = useLocationContext()
  const { showToast } = useToast()
  
  const [fleet, setFleet] = useState<TransporterVehicle[]>([
    { id: 'v1', model: 'Tata Ace Gold (Chhota Hathi)', capacityTons: 1.5, capacityBags: 30, ratePerKm: 28, status: 'available', location: `${activeHub.district} Yard` },
    { id: 'v2', model: 'Mahindra Bolero Maxi Truck', capacityTons: 2.5, capacityBags: 50, ratePerKm: 34, status: 'available', location: activeHub.primaryMandi },
    { id: 'v3', model: 'Eicher Pro 2049 (14ft Intermediate)', capacityTons: 5.0, capacityBags: 100, ratePerKm: 42, status: 'on_route', location: `${activeHub.district} State Highway` },
    { id: 'v4', model: 'Tata 10-Wheeler Multi-Axle (24ft)', capacityTons: 16.0, capacityBags: 320, ratePerKm: 65, status: 'maintenance', location: `${activeHub.state} Regional Terminal` },
  ])
  const [calcDistance, setCalcDistance] = useState(50)
  const [dieselPrice] = useState(92.5)

  // Toggle vehicle status
  const toggleStatus = (id: string) => {
    setFleet((prev) =>
      prev.map((v) => {
        if (v.id !== id) return v
        const nextStatus = v.status === 'available' ? 'on_route' : v.status === 'on_route' ? 'maintenance' : 'available'
        showToast(`Vehicle ${v.model} status updated to: ${nextStatus.toUpperCase()}`, 'info')
        return { ...v, status: nextStatus }
      }),
    )
  }

  // Estimated fuel cost & revenue for calculated distance
  const estTripRevenue = calcDistance * 34 + 400
  const estFuelLiters = (calcDistance / 9.5) * 2 // Round trip fuel consumption
  const estFuelCost = Math.round(estFuelLiters * dieselPrice)
  const estNetProfit = estTripRevenue - estFuelCost - 200 // Toll & maintenance

  return (
    <div className="stack anim-fade-in">
      <RoleSwitcherBar activeRole="transport" />

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{ fontSize: '26px' }}>🚛</span>
            <h1 style={{ margin: 0 }}>Transporter &amp; Logistics Workspace</h1>
          </div>
          <p className="lede" style={{ margin: '4px 0 0' }}>
            Manage commercial freight fleet, receive live farmer load requests, and simulate diesel route margins.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <Badge tone="success">
            {fleet.filter((v) => v.status === 'available').length} Vehicles Available Today
          </Badge>
          <Badge tone="info">Transporter Role</Badge>
        </div>
      </div>

      {/* Metric Cards Row */}
      <div className="card-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
        <div className="card" style={{ padding: 'var(--space-3)' }}>
          <span className="text-caption muted">Total Registered Fleet</span>
          <div style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 800, color: 'var(--color-brand)' }}>
            {fleet.length} <span style={{ fontSize: '13px', fontWeight: 400 }}>Vehicles</span>
          </div>
        </div>
        <div className="card" style={{ padding: 'var(--space-3)' }}>
          <span className="text-caption muted">Average Freight Tariff</span>
          <div style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 800, color: 'var(--color-brand)' }}>
            ₹38 <span style={{ fontSize: '13px', fontWeight: 400 }}>/ km</span>
          </div>
        </div>
        <div className="card" style={{ padding: 'var(--space-3)' }}>
          <span className="text-caption muted">Pending Freight Requests</span>
          <div style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 800, color: '#D97706' }}>
            3 <span style={{ fontSize: '13px', fontWeight: 400 }}>Inward Loads</span>
          </div>
        </div>
        <div className="card" style={{ padding: 'var(--space-3)' }}>
          <span className="text-caption muted">Diesel Index Benchmark</span>
          <div style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 800, color: 'var(--color-text)' }}>
            ₹{dieselPrice} <span style={{ fontSize: '13px', fontWeight: 400 }}>/ Litre</span>
          </div>
        </div>
      </div>

      {/* Fleet Management Card */}
      <Card
        title="🚛 Registered Commercial Vehicle Fleet"
        badge={
          <Button
            variant="primary"
            className="btn--sm"
            onClick={() => showToast('Vehicle registration window opened. Submit RC & Insurance details.', 'info')}
          >
            + Add New Truck
          </Button>
        }
      >
        <div className="table-wrap">
          <table className="table" aria-label="Fleet vehicle table">
            <thead>
              <tr>
                <th>Vehicle Model</th>
                <th>Capacity</th>
                <th>Tariff Rate</th>
                <th>Current Depot / Location</th>
                <th>Operating Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {fleet.map((v) => (
                <tr key={v.id}>
                  <td>
                    <strong>{v.model}</strong>
                  </td>
                  <td className="num">
                    {v.capacityTons} Tonnes ({v.capacityBags} Bags)
                  </td>
                  <td className="num text-strong">₹{v.ratePerKm} / km</td>
                  <td className="muted">{v.location}</td>
                  <td>
                    <Badge
                      tone={
                        v.status === 'available'
                          ? 'success'
                          : v.status === 'on_route'
                            ? 'warning'
                            : 'neutral'
                      }
                    >
                      {v.status === 'available'
                        ? '🟢 Available Today'
                        : v.status === 'on_route'
                          ? '🟡 En Route'
                          : '🔴 Maintenance'}
                    </Badge>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn btn--secondary btn--sm"
                      onClick={() => toggleStatus(v.id)}
                    >
                      Toggle Status ⇄
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Inward Farmer Load Requests */}
      <Card title={`📦 Live Farmer Freight Requests near ${activeHub.district} (${activeHub.state})`}>
        <div className="stack">
          {[
            {
              id: 'load1',
              farmer: 'Local Producer Group',
              crop: `${activeHub.dominantCrop} (60 Quintals / 120 Bags)`,
              route: `${activeHub.district} Farmgate ➔ ${activeHub.primaryMandi} (38 km)`,
              budget: '₹2,400',
              timing: 'Tomorrow Morning 07:00 AM',
            },
            {
              id: 'load2',
              farmer: 'Suresh Reddy & Co.',
              crop: 'Raw Cotton / Grain (80 Quintals)',
              route: `${activeHub.district} Outskirts ➔ Regional Hub (65 km)`,
              budget: '₹3,400',
              timing: 'Within 48 Hours',
            },
            {
              id: 'load3',
              farmer: 'Mahendra Singh',
              crop: 'Grade-A Milling Produce (120 Quintals)',
              route: `Local APMC ➔ State Terminal (55 km)`,
              budget: '₹4,100',
              timing: 'Immediate Dispatch',
            },
          ].map((item) => (
            <div
              key={item.id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 'var(--space-3)',
                padding: 'var(--space-3)',
                background: 'var(--color-surface-alt)',
                borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--color-border-subtle)',
              }}
            >
              <div>
                <strong style={{ fontSize: 'var(--font-size-md)' }}>{item.crop}</strong>
                <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
                  📍 {item.route} · Farmer: {item.farmer}
                </div>
                <span className="text-caption muted">⏱️ Timing: {item.timing}</span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                <div style={{ textAlign: 'right' }}>
                  <span className="text-caption muted">Offered Freight:</span>
                  <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 800, color: 'var(--color-brand)' }}>
                    {item.budget}
                  </div>
                </div>

                <Button
                  variant="primary"
                  className="btn--sm"
                  onClick={() => showToast(`Trip accepted for ${item.farmer}! Booking confirmation dispatched to your SMS.`, 'success')}
                >
                  Accept Freight Job ✓
                </Button>
                <Button
                  variant="secondary"
                  className="btn--sm"
                  onClick={() => showToast(`Counter-quote modal opened for ${item.farmer}.`, 'info')}
                >
                  Counter-Quote
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Diesel Fuel & Route Margin Estimator */}
      <Card title="⛽ Diesel Fuel &amp; Trip Margin Calculator" accent>
        <div className="card-grid" style={{ alignItems: 'center' }}>
          <div>
            <label htmlFor="route-dist-slider" className="field__label">
              One-Way Route Distance: <strong className="num">{calcDistance} km</strong>
            </label>
            <input
              id="route-dist-slider"
              type="range"
              min="10"
              max="250"
              step="5"
              className="range-slider"
              value={calcDistance}
              onChange={(e) => setCalcDistance(Number(e.target.value))}
            />
            <span className="field__hint">
              Round trip: {calcDistance * 2} km · Estimated fuel consumption: {estFuelLiters.toFixed(1)} Litres @ ₹{dieselPrice}/L
            </span>
          </div>

          <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap' }}>
            <div>
              <span className="text-caption muted">Gross Revenue:</span>
              <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 800, color: 'var(--color-brand)' }}>
                ₹{estTripRevenue.toLocaleString('en-IN')}
              </div>
            </div>
            <div>
              <span className="text-caption muted">Est. Fuel Cost:</span>
              <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 800, color: 'var(--color-error)' }}>
                -₹{estFuelCost.toLocaleString('en-IN')}
              </div>
            </div>
            <div>
              <span className="text-caption muted">Net Trip Margin:</span>
              <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 800, color: '#16A34A' }}>
                ₹{estNetProfit.toLocaleString('en-IN')}
              </div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}

/* ============================================================
   3. STORAGE & WAREHOUSE DASHBOARD (गोदाम कार्यक्षेत्र)
   ============================================================ */

function StorageDashboard() {
  const { activeHub } = useLocationContext()
  const { showToast } = useToast()
  const [totalBags] = useState(20000)
  const [occupiedBags, setOccupiedBags] = useState(14500)
  const [wdraCertified, setWdraCertified] = useState(true)

  const availableBags = totalBags - occupiedBags
  const percentOccupied = Math.round((occupiedBags / totalBags) * 100)

  return (
    <div className="stack anim-fade-in">
      <RoleSwitcherBar activeRole="storage" />

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{ fontSize: '26px' }}>🏭</span>
            <h1 style={{ margin: 0 }}>Warehouse &amp; Cold Storage Operator Workspace</h1>
          </div>
          <p className="lede" style={{ margin: '4px 0 0' }}>
            Track chamber capacity, set rental tariffs, register WDRA negotiable receipts (e-NWR), and alert farmers at peak selling windows.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <Badge tone="success">
            {availableBags.toLocaleString('en-IN')} Bags Space Available
          </Badge>
          <Badge tone="info">Storage Operator</Badge>
        </div>
      </div>

      {/* Capacity Progress Meter Card */}
      <Card title="📊 Warehouse Space Utilization &amp; Chamber Telematics" accent>
        <div style={{ marginBottom: 'var(--space-4)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-1)' }}>
            <span style={{ fontSize: 'var(--font-size-md)', fontWeight: 700 }}>
              Space Utilization: {percentOccupied}% Full ({occupiedBags.toLocaleString('en-IN')} / {totalBags.toLocaleString('en-IN')} Bags)
            </span>
            <span className="num" style={{ color: 'var(--color-brand)', fontWeight: 700 }}>
              {availableBags.toLocaleString('en-IN')} Bags Vacant
            </span>
          </div>

          <div className="progress-bar" style={{ height: '16px' }}>
            <div
              className={`progress-bar__fill ${percentOccupied > 80 ? 'progress-bar__fill--warning' : 'progress-bar__fill--success'}`}
              style={{ width: `${percentOccupied}%` }}
            />
          </div>
        </div>

        {/* Real-time Chamber Telematics */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: 'var(--space-3)',
            background: 'var(--color-surface-alt)',
            padding: 'var(--space-3)',
            borderRadius: 'var(--radius-lg)',
          }}
        >
          <div>
            <span className="text-caption muted">Cold Chamber A (Onion/Potato)</span>
            <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 800, color: 'var(--color-brand)' }}>
              2.2°C <span style={{ fontSize: '12px', fontWeight: 400 }}>(Target: 2°C–4°C)</span>
            </div>
          </div>
          <div>
            <span className="text-caption muted">Chamber Humidity</span>
            <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 800, color: 'var(--color-brand)' }}>
              68% RH <span style={{ fontSize: '12px', fontWeight: 400 }}>(Optimal)</span>
            </div>
          </div>
          <div>
            <span className="text-caption muted">Dry Godown 1 (Wheat/Paddy)</span>
            <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 800, color: 'var(--color-text)' }}>
              24.1°C <span style={{ fontSize: '12px', fontWeight: 400 }}>(Aeration Active)</span>
            </div>
          </div>
          <div>
            <span className="text-caption muted">WDRA Certification</span>
            <div style={{ marginTop: '2px' }}>
              <Badge tone="success">WDRA Certified #WDRA/MH/2024</Badge>
            </div>
          </div>
        </div>
      </Card>

      {/* Stock Release Advisory Card */}
      <div
        style={{
          background: 'linear-gradient(135deg, #153F35 0%, #26745A 100%)',
          color: '#FFFFFF',
          borderRadius: 'var(--radius-xl)',
          padding: 'var(--space-4) var(--space-5)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 'var(--space-3)',
        }}
      >
        <div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: '4px' }}>
            <span style={{ color: '#E9B949' }}>🔔</span>
            <strong style={{ fontSize: 'var(--font-size-md)', color: '#FFFFFF' }}>
              Stock Release Window Advisory for {activeHub.dominantCrop} ({activeHub.district})
            </strong>
          </div>
          <p style={{ margin: 0, fontSize: 'var(--font-size-sm)', opacity: 0.9 }}>
            Mandi price spreads suggest an optimal unloading window for <strong>{activeHub.dominantCrop}</strong> in upcoming trading sessions at {activeHub.primaryMandi}.
            Notify registered storing farmers to evaluate dispatches against storage rental fees.
          </p>
        </div>

        <Button
          variant="gold"
          className="btn--sm"
          onClick={() => showToast('Automated SMS notification sent to 24 storing farmers regarding the upcoming peak price window.', 'success')}
        >
          Send Peak Alert to Farmers 📢
        </Button>
      </div>

      {/* Inward Farmer Storage Reservations */}
      <Card title="📥 Pending Inward Farmer Storage Requests">
        <div className="stack">
          {[
            {
              id: 'req1',
              farmer: 'Bhaskar Rao',
              crop: 'Rabi Red Onion',
              quantity: '150 Bags (75 Quintals)',
              desiredChamber: 'Chamber A (Cold Store)',
              duration: '30 Days',
              inwardDate: 'Nov 03, 2026',
            },
            {
              id: 'req2',
              farmer: 'Anand Shinde',
              crop: 'Lokwan Milling Wheat',
              quantity: '300 Bags (150 Quintals)',
              desiredChamber: 'Dry Godown 1',
              duration: '60 Days',
              inwardDate: 'Nov 05, 2026',
            },
          ].map((r) => (
            <div
              key={r.id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 'var(--space-3)',
                padding: 'var(--space-3)',
                background: 'var(--color-surface-alt)',
                borderRadius: 'var(--radius-lg)',
              }}
            >
              <div>
                <strong style={{ fontSize: 'var(--font-size-md)' }}>{r.crop} · {r.quantity}</strong>
                <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
                  Farmer: {r.farmer} · {r.desiredChamber} · Expected Arrival: {r.inwardDate}
                </div>
                <span className="text-caption muted">Duration: {r.duration}</span>
              </div>

              <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                <Button
                  variant="primary"
                  className="btn--sm"
                  onClick={() => {
                    setOccupiedBags((prev) => prev + 150)
                    showToast(`Reservation approved for ${r.farmer}. Electronic Gate Pass dispatched.`, 'success')
                  }}
                >
                  Approve Space Reservation ✓
                </Button>
                <Button
                  variant="secondary"
                  className="btn--sm"
                  onClick={() => showToast(`e-NWR pledge loan receipt issued for ${r.farmer}.`, 'info')}
                >
                  Issue e-NWR Receipt 📄
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Facility Tariff Management */}
      <Card title="⚙️ Warehouse Tariff &amp; Banking Accreditation">
        <div className="card-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
          <div>
            <span className="field__label">Dry Godown Tariff</span>
            <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 800 }}>₹18 / bag / month</div>
            <span className="field__hint">Suitable for Wheat, Soybean, Paddy</span>
          </div>
          <div>
            <span className="field__label">Cold Storage Tariff</span>
            <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 800 }}>₹32 / bag / month</div>
            <span className="field__hint">Suitable for Onion, Potato, Fruits</span>
          </div>
          <div>
            <span className="field__label">e-NWR Bank Loan Eligibility</span>
            <div style={{ marginTop: 'var(--space-1)' }}>
              <button
                type="button"
                className={`btn btn--sm ${wdraCertified ? 'btn--primary' : 'btn--secondary'}`}
                onClick={() => setWdraCertified(!wdraCertified)}
              >
                {wdraCertified ? '✓ Enabled (Up to 70% Bank Loan)' : 'Disabled'}
              </button>
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}

/* ============================================================
   4. BUYER & TRADER DASHBOARD (खरीदार कार्यक्षेत्र)
   ============================================================ */

function BuyerDashboard() {
  const { activeHub } = useLocationContext()
  const { showToast } = useToast()
  const [showPostModal, setShowPostModal] = useState(false)
  const [reqCrop, setReqCrop] = useState(activeHub.dominantCrop)
  const [reqQty, setReqQty] = useState('50')
  const [reqPrice, setReqPrice] = useState('2500')

  return (
    <div className="stack anim-fade-in">
      <RoleSwitcherBar activeRole="buyer" />

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{ fontSize: '26px' }}>🤝</span>
            <h1 style={{ margin: 0 }}>Buyer &amp; Institutional Trader Workspace</h1>
          </div>
          <p className="lede" style={{ margin: '4px 0 0' }}>
            Post commercial buying tenders, browse verified farmer produce lots, and negotiate transparent procurement contracts.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <Button variant="primary" onClick={() => setShowPostModal(true)}>
            + Post Buying Demand
          </Button>
          <Badge tone="info">Corporate Buyer</Badge>
        </div>
      </div>

      {/* Metric Cards Row */}
      <div className="card-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
        <div className="card" style={{ padding: 'var(--space-3)' }}>
          <span className="text-caption muted">Active Demands Posted</span>
          <div style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 800, color: 'var(--color-brand)' }}>
            4 <span style={{ fontSize: '13px', fontWeight: 400 }}>Requirements</span>
          </div>
        </div>
        <div className="card" style={{ padding: 'var(--space-3)' }}>
          <span className="text-caption muted">Sourced Produce This Month</span>
          <div style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 800, color: 'var(--color-brand)' }}>
            480 <span style={{ fontSize: '13px', fontWeight: 400 }}>Quintals</span>
          </div>
        </div>
        <div className="card" style={{ padding: 'var(--space-3)' }}>
          <span className="text-caption muted">Farmer Inquiries Received</span>
          <div style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 800, color: '#D97706' }}>
            12 <span style={{ fontSize: '13px', fontWeight: 400 }}>Farmer Bids</span>
          </div>
        </div>
        <div className="card" style={{ padding: 'var(--space-3)' }}>
          <span className="text-caption muted">Trade Settlement Status</span>
          <div style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 800, color: '#16A34A' }}>
            100% <span style={{ fontSize: '13px', fontWeight: 400 }}>RTGS / Bank NEFT</span>
          </div>
        </div>
      </div>

      {/* Active Buyer Procurement Requirements */}
      <Card
        title="📋 Your Active Institutional Procurement Requirements"
        badge={<Badge tone="success">Verified APMC Commercial Entity</Badge>}
      >
        <div className="stack">
          {[
            {
              id: 'req1',
              commodity: 'Onion (Nashik Red / Garwa)',
              minQty: '30 Quintals',
              price: '₹2,520 / qtl',
              location: 'Nashik Hub, Maharashtra',
              payment: 'T+2 Days Direct Bank NEFT',
              inquiries: 5,
            },
            {
              id: 'req2',
              commodity: 'Sharbati Milling Wheat',
              minQty: '50 Quintals',
              price: '₹2,460 / qtl',
              location: 'Indore Processing Unit',
              payment: 'Immediate RTGS on Weighment Slip',
              inquiries: 7,
            },
            {
              id: 'req3',
              commodity: 'Tomato (Hybrid A-Grade)',
              minQty: '20 Quintals',
              price: '₹2,180 / qtl',
              location: 'Pune Fulfillment Center',
              payment: 'Weekly Settlement',
              inquiries: 3,
            },
          ].map((item) => (
            <div
              key={item.id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 'var(--space-3)',
                padding: 'var(--space-3)',
                background: 'var(--color-surface-alt)',
                borderRadius: 'var(--radius-lg)',
              }}
            >
              <div>
                <strong style={{ fontSize: 'var(--font-size-md)' }}>{item.commodity}</strong>
                <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
                  Target: {item.price} · Min Qty: {item.minQty} · 📍 {item.location}
                </div>
                <span className="text-caption muted">Payment Terms: {item.payment}</span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                <Badge tone="gold">💬 {item.inquiries} Farmers Interested</Badge>
                <Button
                  variant="secondary"
                  className="btn--sm"
                  onClick={() => showToast(`Opening inquiries list for ${item.commodity}.`, 'info')}
                >
                  Review Bids →
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Post Requirement Modal */}
      {showPostModal && (
        <Card title="📝 Post New Procurement Tender" accent>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              setShowPostModal(false)
              showToast(`Procurement demand for ${reqCrop} (${reqQty} qtl @ ₹${reqPrice}/qtl) published to farmer marketplace!`, 'success')
            }}
            className="stack"
          >
            <div className="card-grid">
              <div className="field">
                <label className="field__label">Commodity</label>
                <input
                  className="input"
                  value={reqCrop}
                  onChange={(e) => setReqCrop(e.target.value)}
                  required
                />
              </div>
              <div className="field">
                <label className="field__label">Min Quantity (Quintals)</label>
                <input
                  type="number"
                  className="input"
                  value={reqQty}
                  onChange={(e) => setReqQty(e.target.value)}
                  required
                />
              </div>
              <div className="field">
                <label className="field__label">Target Buying Price (₹/qtl)</label>
                <input
                  type="number"
                  className="input"
                  value={reqPrice}
                  onChange={(e) => setReqPrice(e.target.value)}
                  required
                />
              </div>
            </div>
            <div className="inline-actions">
              <Button type="submit" variant="primary">Publish Requirement</Button>
              <Button variant="secondary" onClick={() => setShowPostModal(false)}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

      {/* Live Market Spot Benchmark */}
      <div className="card-grid">
        <MarketPanel />
        <ReferencePanel />
      </div>
    </div>
  )
}

/* ============================================================
   5. ADMIN DASHBOARD
   ============================================================ */

function AdminDashboard() {
  return (
    <div className="stack anim-fade-in">
      <RoleSwitcherBar activeRole="farmer" />

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
        <div>
          <h1>Administrator Console</h1>
          <p className="lede">
            System governance, reference data verification, and platform integrity management.
          </p>
        </div>
        <Badge tone="warning">Admin Privileges</Badge>
      </div>

      <div className="card-grid">
        <div className="card card--interactive" onClick={() => navigate('/reference')}>
          <h3>🗂️ Reference Data Management</h3>
          <p className="text-body-sm">
            Inspect official administrative boundaries (States, Districts, Mandis, Commodities).
          </p>
          <Button variant="primary" className="btn--sm" onClick={() => navigate('/reference')}>
            Reference Inspector →
          </Button>
        </div>

        <div className="card card--interactive" onClick={() => navigate('/schemes')}>
          <h3>🏛️ Government Schemes Catalog</h3>
          <p className="text-body-sm">
            Audit verified welfare schemes, official URLs, and eligibility rules.
          </p>
          <Button variant="secondary" className="btn--sm" onClick={() => navigate('/schemes')}>
            Inspect Schemes →
          </Button>
        </div>
      </div>

      <div className="card-grid">
        <MarketPanel />
        <ReferencePanel />
      </div>
    </div>
  )
}

function RoleShell({ role }: { role: DashboardRole }) {
  if (role === 'buyer') return <BuyerDashboard />
  if (role === 'transport') return <TransportDashboard />
  if (role === 'storage') return <StorageDashboard />
  if (role === 'admin') return <AdminDashboard />
  return <FarmerDashboard name={null} />
}

export function DashboardPage({ path }: { path: string }) {
  const { t } = useTranslation()
  const { user } = useAuth()

  const roleSegment = path.split('/')[2]?.split('?')[0] ?? ''

  // If a specific role path is requested (e.g. #/dashboard/transport), show it directly
  if (roleSegment) {
    if (isDashboardRole(roleSegment)) {
      return <RoleShell role={roleSegment} />
    }
    return (
      <div className="stack anim-fade-in">
        <h1>{t('error.notFound.title')}</h1>
        <p className="lede">{t('error.notFound.body')}</p>
        <p>
          <Button variant="secondary" onClick={() => navigate('/dashboard')}>
            {t('dash.title')}
          </Button>
        </p>
      </div>
    )
  }

  // Default: if user is signed in, show their role; otherwise default to Farmer workspace
  const ownRole: DashboardRole = user
    ? (user.roles.map((role) => ROLE_TO_DASHBOARD[role]).find(Boolean) ?? 'farmer')
    : 'farmer'

  return <RoleShell role={ownRole} />
}
