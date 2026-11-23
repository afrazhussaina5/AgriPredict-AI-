import { useState } from 'react'
import { Badge, Button, Card } from '../components/ui'
import { useToast } from '../components/Toast'
import { useTranslation } from '../i18n/useTranslation'
import { navigate } from '../router'
import { useLocationContext } from '../context/LocationContext'

type TransportProvider = {
  id: string
  providerName: string
  vehicleType: string
  capacityTons: number
  capacityBags: number
  baseRatePerKm: number
  serviceRadiusKm: number
  location: string
  rating: number
  verified: boolean
  availableNow: boolean
}

type StorageFacility = {
  id: string
  facilityName: string
  facilityType: 'Cold Storage' | 'Dry Godown (WDRA)' | 'Ventilated Onion Chawl'
  totalCapacityBags: number
  occupiedBags: number
  ratePerBagMonth: number
  wdraCertified: boolean
  eNwrLoanEligible: boolean
  location: string
  suitableCommodities: string
}

const VEHICLES: TransportProvider[] = [
  {
    id: 'v1',
    providerName: 'Kisan Express Logistics (Ramesh G.)',
    vehicleType: 'Tata Ace Gold / Bolero Maxi Truck',
    capacityTons: 1.5,
    capacityBags: 30,
    baseRatePerKm: 28,
    serviceRadiusKm: 60,
    location: 'Pimpalgaon Hub, Nashik',
    rating: 4.8,
    verified: true,
    availableNow: true,
  },
  {
    id: 'v2',
    providerName: 'Jai Kisan Freight Services (Sunil Patil)',
    vehicleType: 'Eicher Pro 2049 (Intermediate 14ft)',
    capacityTons: 5.0,
    capacityBags: 100,
    baseRatePerKm: 42,
    serviceRadiusKm: 150,
    location: 'Lasalgaon Mandi Yard',
    rating: 4.9,
    verified: true,
    availableNow: true,
  },
  {
    id: 'v3',
    providerName: 'National Agri Transport Carriers',
    vehicleType: '10-Wheeler Multi-Axle Truck (24ft)',
    capacityTons: 16.0,
    capacityBags: 320,
    baseRatePerKm: 65,
    serviceRadiusKm: 500,
    location: 'Mumbai - Nashik Expressway Terminal',
    rating: 4.7,
    verified: true,
    availableNow: false,
  },
]

const FACILITIES: StorageFacility[] = [
  {
    id: 's1',
    facilityName: 'Sahyadri Farmers Post-Harvest Cold Store',
    facilityType: 'Cold Storage',
    totalCapacityBags: 20000,
    occupiedBags: 14500,
    ratePerBagMonth: 32,
    wdraCertified: true,
    eNwrLoanEligible: true,
    location: 'Mohadi Industrial Cluster, Nashik',
    suitableCommodities: 'Potato, Fruits, Vegetables, Seeds',
  },
  {
    id: 's2',
    facilityName: 'Central Warehousing Corporation (CWC Yard #4)',
    facilityType: 'Dry Godown (WDRA)',
    totalCapacityBags: 50000,
    occupiedBags: 32000,
    ratePerBagMonth: 18,
    wdraCertified: true,
    eNwrLoanEligible: true,
    location: 'Niphad Railway Siding, Nashik',
    suitableCommodities: 'Wheat, Paddy, Soybean, Pulses',
  },
  {
    id: 's3',
    facilityName: 'Dindori Taluka Cooperative Ventilated Chawl',
    facilityType: 'Ventilated Onion Chawl',
    totalCapacityBags: 8000,
    occupiedBags: 3600,
    ratePerBagMonth: 22,
    wdraCertified: false,
    eNwrLoanEligible: false,
    location: 'Dindori APMC Sub-Yard',
    suitableCommodities: 'Rabi / Red Onion, Garlic',
  },
]

const INR = (n: number) => '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 0 })

export function ServicesPage() {
  const { t } = useTranslation()
  const { showToast } = useToast()
  const { activeHub } = useLocationContext()
  const [activeTab, setActiveTab] = useState<'transport' | 'storage'>('transport')
  const [bookedTransportIds, setBookedTransportIds] = useState<Set<string>>(new Set())
  const [inquiredStorageIds, setInquiredStorageIds] = useState<Set<string>>(new Set())

  // Quick Trip Cost Estimator
  const [testDistanceKm, setTestDistanceKm] = useState<number>(45)

  return (
    <div className="wrapper section anim-fade-in">
      <div className="stack">
        <div>
          <p className="eyebrow mb-1">{t('nav.services')} · 📍 {activeHub.name}</p>
          <h1>{t('services.title')}</h1>
          <p className="lede">
            Freight transport and WDRA cold storage facilities serving <strong>{activeHub.district} ({activeHub.state})</strong> and surrounding APMC yards.
          </p>
        </div>

        {/* Sample data disclaimer */}
        <div style={{
          background: 'var(--color-warm-soft)',
          border: '1px solid var(--color-warm-bg)',
          borderRadius: 'var(--radius-md)',
          padding: 'var(--space-3) var(--space-4)',
          display: 'flex',
          gap: 'var(--space-2)',
          fontSize: 'var(--font-size-xs)',
          color: 'var(--color-warm-ink)',
        }}>
          <span style={{ fontSize: 16, lineHeight: 1 }}>⚠️</span>
          <span>
            <strong>Sample listings for demonstration.</strong>{' '}
            In production, providers are verified through GST and vehicle registration.
            All prices shown are estimated — confirm with the actual transporter before booking.
          </span>
        </div>

        {/* Tab Switcher */}
        <div className="inline-actions">
          <Button
            variant={activeTab === 'transport' ? 'primary' : 'secondary'}
            onClick={() => setActiveTab('transport')}
          >
            🚚 {t('services.transportTab')}
          </Button>
          <Button
            variant={activeTab === 'storage' ? 'primary' : 'secondary'}
            onClick={() => setActiveTab('storage')}
          >
            🏭 {t('services.storageTab')}
          </Button>
        </div>

        {/* ===================== TRANSPORT TAB ===================== */}
        {activeTab === 'transport' && (
          <div className="stack anim-slide-up">
            {/* Quick Estimator Card */}
            <Card title="Quick Freight Rate Estimator" accent>
              <div className="card-grid" style={{ alignItems: 'center' }}>
                <div>
                  <label htmlFor="trip-dist" className="field__label">
                    Estimated Trip Distance to Mandi:{' '}
                    <strong className="num">{testDistanceKm} km</strong>
                  </label>
                  <input
                    id="trip-dist"
                    type="range"
                    min="5"
                    max="200"
                    step="5"
                    className="range-slider"
                    value={testDistanceKm}
                    onChange={(e) => setTestDistanceKm(Number(e.target.value))}
                  />
                  <span className="field__hint">
                    Estimate based on typical light truck rates (₹28–65/km). Always get a confirmed quote.
                  </span>
                </div>
                <div className="metric-group">
                  <span className="text-caption muted">Estimated Mini-Truck Trip:</span>
                  <span
                    className="metric-group__val text-strong"
                    style={{ color: 'var(--color-primary-strong)' }}
                  >
                    {INR(testDistanceKm * 28 + 350)}
                  </span>
                  <span className="metric-group__unit">includes base fuel + loading support</span>
                </div>
              </div>
            </Card>

            {/* Transport Providers List */}
            <div className="stack">
              {VEHICLES.map((v) => {
                const estCost = testDistanceKm * v.baseRatePerKm + 350

                return (
                  <div key={v.id} className="card">
                    <div className="card__header">
                      <div>
                        <h3 style={{ margin: 0 }}>{v.providerName}</h3>
                        <p className="text-caption muted" style={{ margin: 'var(--space-1) 0 0' }}>
                          📍 {v.location} · Radius: {v.serviceRadiusKm} km · ⭐ {v.rating} rating
                        </p>
                      </div>
                      <div>
                        {v.availableNow ? (
                          <Badge tone="success" className="badge--pulse">
                            <span className="pulse-dot" /> Available Today
                          </Badge>
                        ) : (
                          <Badge tone="neutral">Advance Booking</Badge>
                        )}
                      </div>
                    </div>

                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                        gap: 'var(--space-3)',
                        padding: 'var(--space-3)',
                        background: 'var(--color-surface-alt)',
                        borderRadius: 'var(--radius-md)',
                        margin: 'var(--space-3) 0',
                      }}
                    >
                      <div>
                        <span className="eyebrow">Vehicle Type</span>
                        <p className="text-sm text-strong" style={{ margin: 'var(--space-1) 0 0' }}>
                          {v.vehicleType}
                        </p>
                      </div>
                      <div>
                        <span className="eyebrow">Capacity</span>
                        <p className="text-strong num" style={{ margin: 'var(--space-1) 0 0' }}>
                          {v.capacityTons}T / {v.capacityBags} bags
                        </p>
                      </div>
                      <div>
                        <span className="eyebrow">Base Rate</span>
                        <p className="text-strong num" style={{ margin: 'var(--space-1) 0 0' }}>
                          ₹{v.baseRatePerKm}/km
                        </p>
                      </div>
                      <div>
                        <span className="eyebrow">Est. Cost ({testDistanceKm} km)</span>
                        <p
                          className="text-strong num"
                          style={{ margin: 'var(--space-1) 0 0', color: 'var(--color-brand)' }}
                        >
                          {INR(estCost)}
                        </p>
                      </div>
                    </div>

                    <div
                      className="card__footer"
                      style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                    >
                      <span className="text-caption muted">
                        {v.verified ? '✅ Identity & Vehicle Verified' : 'Verification Pending'}
                      </span>

                      {bookedTransportIds.has(v.id) ? (
                        <Badge tone="success">✓ Booking Request Sent!</Badge>
                      ) : (
                        <Button
                          variant="primary"
                          className="btn--sm"
                          onClick={() => {
                            setBookedTransportIds((prev) => new Set([...prev, v.id]))
                            showToast(
                              `Booking request sent to ${v.providerName}. They'll contact you within 2 hours.`,
                              'success'
                            )
                          }}
                        >
                          🚚 Book / Request Quote
                        </Button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* ===================== STORAGE TAB ===================== */}
        {activeTab === 'storage' && (
          <div className="stack anim-slide-up">
            <div className="stack">
              {FACILITIES.map((f) => {
                const percentOccupied = Math.round((f.occupiedBags / f.totalCapacityBags) * 100)
                const availableBags = f.totalCapacityBags - f.occupiedBags

                return (
                  <div key={f.id} className="card">
                    <div className="card__header">
                      <div>
                        <h3 style={{ margin: 0 }}>{f.facilityName}</h3>
                        <p className="text-caption muted" style={{ margin: 'var(--space-1) 0 0' }}>
                          📍 {f.location} · {f.facilityType}
                        </p>
                      </div>
                      <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                        {f.wdraCertified && <Badge tone="info">WDRA Certified</Badge>}
                        {f.eNwrLoanEligible && <Badge tone="success">Bank Loan Eligible (e-NWR)</Badge>}
                      </div>
                    </div>

                    <div style={{ margin: 'var(--space-3) 0' }}>
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          marginBottom: 'var(--space-1)',
                        }}
                      >
                        <span className="text-sm text-secondary">
                          Space Utilization: <strong>{percentOccupied}% Full</strong>
                        </span>
                        <span className="text-sm num text-strong">
                          {availableBags.toLocaleString('en-IN')} Bags Available
                        </span>
                      </div>
                      <div className="progress-bar">
                        <div
                          className={`progress-bar__fill ${
                            percentOccupied > 80
                              ? 'progress-bar__fill--warning'
                              : 'progress-bar__fill--success'
                          }`}
                          style={{ width: `${percentOccupied}%` }}
                        />
                      </div>
                    </div>

                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                        gap: 'var(--space-3)',
                        padding: 'var(--space-3)',
                        background: 'var(--color-surface-alt)',
                        borderRadius: 'var(--radius-md)',
                        margin: 'var(--space-2) 0',
                      }}
                    >
                      <div>
                        <span className="eyebrow">Monthly Rent</span>
                        <p className="text-strong num" style={{ margin: 'var(--space-1) 0 0' }}>
                          ₹{f.ratePerBagMonth} / bag / month
                        </p>
                      </div>
                      <div>
                        <span className="eyebrow">Suitable Crops</span>
                        <p className="text-sm text-strong" style={{ margin: 'var(--space-1) 0 0' }}>
                          {f.suitableCommodities}
                        </p>
                      </div>
                      <div>
                        <span className="eyebrow">Insurance</span>
                        <p className="text-sm text-strong" style={{ margin: 'var(--space-1) 0 0' }}>
                          Fire, Flood &amp; Pest Covered
                        </p>
                      </div>
                    </div>

                    <div
                      className="card__footer"
                      style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                    >
                      <span className="text-caption muted">
                        Weighbridge and scientific grading facility on site
                      </span>

                      {inquiredStorageIds.has(f.id) ? (
                        <Badge tone="success">✓ Space Inquiry Registered! Manager contact sent.</Badge>
                      ) : (
                        <Button
                          variant="primary"
                          className="btn--sm"
                          onClick={() => {
                            setInquiredStorageIds((prev) => new Set([...prev, f.id]))
                            showToast(
                              `Inquiry sent for ${f.facilityName}. Facility manager will call within 24 hours.`,
                              'success'
                            )
                          }}
                        >
                          🏭 Inquire Space / Reserve
                        </Button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Footer Navigation */}
        <div className="inline-actions" style={{ justifyContent: 'space-between' }}>
          <Button variant="secondary" onClick={() => navigate('/market')}>
            ← Check Market Prices
          </Button>
          <Button variant="primary" onClick={() => navigate('/dashboard')}>
            Back to Dashboard →
          </Button>
        </div>
      </div>
    </div>
  )
}
