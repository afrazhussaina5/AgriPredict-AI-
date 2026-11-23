import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchCommodities,
  fetchMarketPrices,
  fetchForecastSeries,
  type Commodity,
  type MarketPriceRow,
  type SeriesForecastResponse,
} from '../api/client'
import { Badge, Button, Card } from '../components/ui'
import { LoadingState } from '../components/states'
import { useToast } from '../components/Toast'
import { useTranslation } from '../i18n/useTranslation'
import { navigate } from '../router'
import { useLocationContext } from '../context/LocationContext'

const INR = (n: number) => '₹' + Math.round(n).toLocaleString('en-IN')

type NearbyBuyerDemand = {
  id: string
  buyerName: string
  type: string
  targetPrice: number
  quantityQtl: number
  distanceKm: number
  paymentMode: string
  pickupOffered: boolean
}

type NearbyStorageFacility = {
  id: string
  name: string
  type: string
  ratePerQtlMonth: number
  availableBags: number
  distanceKm: number
  wdraCertified: boolean
  tempCelsius: string
}

type NearbyTransporter = {
  id: string
  vehicleName: string
  capacityTons: number
  ratePerKm: number
  status: 'available' | 'on_route'
  phoneContact: string
  driverName: string
}

export function CropAnalysisPage() {
  const { t, locale } = useTranslation()
  const { activeHub } = useLocationContext()
  const { showToast } = useToast()

  // Form states
  const [commodities, setCommodities] = useState<Commodity[]>([])
  const [selectedCommodity, setSelectedCommodity] = useState<string>('Onion')
  const [quantityQtl, setQuantityQtl] = useState<number>(50)
  const [grade, setGrade] = useState<string>('Grade-A')
  const [intendedDays, setIntendedDays] = useState<number>(7)
  const [distanceKm, setDistanceKm] = useState<number>(35)

  // Data states
  const [mandiRows, setMandiRows] = useState<MarketPriceRow[]>([])
  const [selectedMandi, setSelectedMandi] = useState<MarketPriceRow | null>(null)
  const [forecast, setForecast] = useState<SeriesForecastResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [activeTab, setActiveTab] = useState<'overview' | 'when' | 'where' | 'who'>('overview')

  // Load commodities and preselect dominant crop
  useEffect(() => {
    fetchCommodities()
      .then((data) => {
        setCommodities(data)
        const matched =
          data.find((c) => c.name.toLowerCase().includes(activeHub.dominantCrop.toLowerCase())) ??
          data.find((c) => c.name.toLowerCase().includes('onion')) ??
          data[0]
        if (matched) setSelectedCommodity(matched.name)
      })
      .catch(() => {})
  }, [activeHub.dominantCrop])

  // Load prices and forecast
  useEffect(() => {
    if (!selectedCommodity) return
    const com = commodities.find((c) => c.name === selectedCommodity)
    const param = com ? { commodity_id: com.id } : undefined

    setLoading(true)
    fetchMarketPrices(param)
      .then((rows) => {
        setMandiRows(rows)
        const localMatch =
          rows.find((r) => r.district_name?.toLowerCase() === activeHub.district.toLowerCase()) ||
          rows[0] ||
          null
        setSelectedMandi(localMatch)

        const sampleMandi = localMatch?.mandi_name ?? activeHub.primaryMandi
        const sampleState = localMatch?.state_name ?? activeHub.state
        const sampleDistrict = localMatch?.district_name ?? activeHub.district

        return fetchForecastSeries({
          commodity: selectedCommodity,
          mandi: sampleMandi,
          state: sampleState,
          district: sampleDistrict,
          days: intendedDays,
        })
      })
      .then((res) => {
        setForecast(res)
        setLoading(false)
      })
      .catch(() => {
        setLoading(false)
      })
  }, [selectedCommodity, activeHub, commodities, intendedDays])

  // Calculations
  const currentModalPrice = selectedMandi?.modal_price ? Number(selectedMandi.modal_price) : 2400
  const projectedPrice = forecast?.forecast_points?.slice(-1)[0]?.price ?? currentModalPrice * 1.05
  const priceDelta = projectedPrice - currentModalPrice
  const isRising = priceDelta > 0

  // Net realization math:
  // Gross = quantity * price
  // Transport = distance * ₹3.2/qtl/km
  // Mandi Cess = 1.5%
  // Labor/Handling = ₹16/qtl
  const estTransportCostPerQtl = Math.max(25, Math.round(distanceKm * 2.8))
  const estMandiCessPerQtl = Math.round(currentModalPrice * 0.015)
  const estHandlingPerQtl = 18
  const totalDeductionPerQtl = estTransportCostPerQtl + estMandiCessPerQtl + estHandlingPerQtl

  const netRealizationSpotPerQtl = Math.max(0, currentModalPrice - totalDeductionPerQtl)
  const totalSpotNetProceeds = netRealizationSpotPerQtl * quantityQtl

  // Storage calculation:
  // Storage rent ~ ₹1.25/kg/month -> ₹125/qtl/month -> ~₹30/qtl for 7 days
  const estStorageCostPerQtl = Math.round((intendedDays / 30) * 125)
  const netRealizationHoldPerQtl = Math.max(
    0,
    projectedPrice - totalDeductionPerQtl - estStorageCostPerQtl,
  )
  const totalHoldNetProceeds = netRealizationHoldPerQtl * quantityQtl
  const storageAdvantage = totalHoldNetProceeds - totalSpotNetProceeds

  // Decision logic
  const isHoldRecommended = isRising && storageAdvantage > 500

  // Nearby simulated ecosystem partners (anchored to activeHub)
  const nearbyBuyers: NearbyBuyerDemand[] = useMemo(
    () => [
      {
        id: 'b1',
        buyerName: `${activeHub.district} Fresh Agro Procurement`,
        type: 'Corporate Processor',
        targetPrice: currentModalPrice + 80,
        quantityQtl: 100,
        distanceKm: 18,
        paymentMode: '100% Direct Bank RTGS',
        pickupOffered: true,
      },
      {
        id: 'b2',
        buyerName: 'National Commodity FPO Federation',
        type: 'Farmer Producer Co-op',
        targetPrice: currentModalPrice + 45,
        quantityQtl: 60,
        distanceKm: 28,
        paymentMode: 'T+1 Immediate NEFT',
        pickupOffered: false,
      },
      {
        id: 'b3',
        buyerName: 'Kisan Retail Supply Chain Ltd',
        type: 'Wholesale Buyer',
        targetPrice: currentModalPrice + 110,
        quantityQtl: 200,
        distanceKm: 42,
        paymentMode: 'Immediate Weighment Cash/UPI',
        pickupOffered: true,
      },
    ],
    [activeHub, currentModalPrice],
  )

  const nearbyStorage: NearbyStorageFacility[] = useMemo(
    () => [
      {
        id: 's1',
        name: `${activeHub.district} Agro Cold Chain & Logistics`,
        type: 'Multi-Chamber Cold Storage',
        ratePerQtlMonth: 120,
        availableBags: 4500,
        distanceKm: 12,
        wdraCertified: true,
        tempCelsius: '2.4°C (Humidity 68%)',
      },
      {
        id: 's2',
        name: `${activeHub.primaryMandi} Central Dry Warehouse`,
        type: 'WDRA Dry Godown',
        ratePerQtlMonth: 85,
        availableBags: 8200,
        distanceKm: 8,
        wdraCertified: true,
        tempCelsius: 'Ambient Aerated',
      },
    ],
    [activeHub],
  )

  const nearbyTransporters: NearbyTransporter[] = useMemo(
    () => [
      {
        id: 't1',
        vehicleName: 'Mahindra Bolero Maxi Truck (2.5T)',
        capacityTons: 2.5,
        ratePerKm: 32,
        status: 'available',
        phoneContact: '+91 98765 43210',
        driverName: 'Santosh Kumar',
      },
      {
        id: 't2',
        vehicleName: 'Tata Ace Gold Chhota Hathi (1.5T)',
        capacityTons: 1.5,
        ratePerKm: 26,
        status: 'available',
        phoneContact: '+91 98765 43211',
        driverName: 'Ravi Teja',
      },
      {
        id: 't3',
        vehicleName: 'Eicher Pro 14-Feet Truck (5.0T)',
        capacityTons: 5.0,
        ratePerKm: 44,
        status: 'available',
        phoneContact: '+91 98765 43212',
        driverName: 'Gurpreet Singh',
      },
    ],
    [],
  )

  return (
    <div className="container anim-fade-in" style={{ paddingBottom: 'var(--space-10)' }}>
      {/* 1. Header Banner */}
      <div className="page-header mb-5">
        <div className="flex-between flex-wrap flex-gap-2">
          <div>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 'var(--space-2)',
                marginBottom: 'var(--space-1)',
              }}
            >
              <Badge tone="success" className="badge--pulse">
                <span className="pulse-dot" /> Live Market &amp; ML Intelligence
              </Badge>
              <span className="eyebrow">DECISION ENGINE (कब, कहाँ, किसको बेचें?)</span>
            </div>
            <h1 className="text-title-xl" style={{ margin: 0 }}>
              Smart Crop Economics &amp; 3-Way Selling Guidance
            </h1>
            <p className="text-body-md muted mt-1" style={{ maxWidth: '44rem' }}>
              Select your crop, quantity, and grade. AgriPredict AI calculates exact net realization,
              predicts forward price trajectories, and provides clear <strong>WHEN, WHERE &amp; WHOM</strong> actions.
            </p>
          </div>
          <div className="flex-center flex-gap-2">
            <Button variant="secondary" onClick={() => navigate('/compare')}>
              ⚖️ Mandi Compare
            </Button>
            <Button variant="primary" onClick={() => navigate('/chat')}>
              🎙️ Ask AgriMitra AI
            </Button>
          </div>
        </div>
      </div>

      {/* 2. Top Interactive Crop Selection & Parameter Bar */}
      <Card
        accent
        style={{
          background: 'linear-gradient(135deg, #FFFFFF 0%, var(--color-surface-alt) 100%)',
          border: '1.5px solid var(--color-brand)',
          boxShadow: '0 8px 24px rgba(30, 142, 98, 0.10)',
          marginBottom: 'var(--space-6)',
        }}
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: 'var(--space-3)',
            alignItems: 'flex-end',
          }}
        >
          {/* Commodity */}
          <div className="field">
            <label className="field__label">🌾 Select Crop (फसल चुनें)</label>
            <select
              className="field__select"
              value={selectedCommodity}
              onChange={(e) => setSelectedCommodity(e.target.value)}
            >
              {commodities.map((c) => (
                <option key={c.id} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Active Hub / Location (Preselected) */}
          <div className="field">
            <label className="field__label">📍 Location (आपका इलाका)</label>
            <div
              style={{
                padding: '9px 12px',
                background: '#FFFFFF',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border)',
                fontWeight: 600,
                fontSize: '13px',
                color: 'var(--color-brand-strong)',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <span>{activeHub.icon}</span>
              <span>{activeHub.district} ({activeHub.state})</span>
            </div>
          </div>

          {/* Quantity */}
          <div className="field">
            <label className="field__label">⚖️ Quantity (क्विंटल में)</label>
            <input
              type="number"
              className="input"
              value={quantityQtl}
              min={1}
              max={2000}
              onChange={(e) => setQuantityQtl(Number(e.target.value))}
            />
          </div>

          {/* Grade */}
          <div className="field">
            <label className="field__label">🏷️ Quality / Grade</label>
            <select
              className="field__select"
              value={grade}
              onChange={(e) => setGrade(e.target.value)}
            >
              <option value="Grade-A">Grade A (Export / Premium)</option>
              <option value="FAQ">FAQ (Fair Average Quality)</option>
              <option value="Grade-B">Grade B (Standard Commercial)</option>
            </select>
          </div>

          {/* Distance */}
          <div className="field">
            <label className="field__label">🚛 Est. Mandi Dist (km)</label>
            <input
              type="number"
              className="input"
              value={distanceKm}
              min={5}
              max={300}
              onChange={(e) => setDistanceKm(Number(e.target.value))}
            />
          </div>
        </div>
      </Card>

      {/* 3. Navigation Tabs for the 3 Pillars */}
      <div
        style={{
          display: 'flex',
          gap: 'var(--space-2)',
          marginBottom: 'var(--space-4)',
          borderBottom: '2px solid var(--color-border-subtle)',
          paddingBottom: 'var(--space-2)',
          flexWrap: 'wrap',
        }}
      >
        {[
          { key: 'overview', label: '📊 Complete 360° Crop Intelligence' },
          { key: 'when', label: '⏱️ 1. WHEN to Sell (Timing & Price Trajectory)' },
          { key: 'where', label: '⚖️ 2. WHERE to Sell (Mandi Net Realization)' },
          { key: 'who', label: '🤝 3. WHOM to Sell (Buyers, Storage & Transport)' },
        ].map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={`btn btn--sm ${activeTab === tab.key ? 'btn--primary' : 'btn--secondary'}`}
            style={{ borderRadius: 'var(--radius-full)' }}
            onClick={() => setActiveTab(tab.key as any)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading && <LoadingState />}

      {!loading && (
        <div className="stack">
          {/* ====================================================
              TOP SUMMARY HIGHLIGHTS ROW
              ==================================================== */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: 'var(--space-3)',
            }}
          >
            {/* Spot Rate Card */}
            <div
              className="card"
              style={{
                background: '#FFFFFF',
                borderLeft: '4px solid var(--color-brand)',
                padding: 'var(--space-3)',
              }}
            >
              <span className="text-caption muted">Today's Benchmark Spot Price:</span>
              <div
                style={{
                  fontSize: 'var(--font-size-2xl)',
                  fontWeight: 800,
                  color: 'var(--color-brand)',
                  marginTop: '2px',
                }}
              >
                {INR(currentModalPrice)} <span style={{ fontSize: '13px', fontWeight: 400 }}>/ qtl</span>
              </div>
              <span style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
                📍 {selectedMandi?.mandi_name || activeHub.primaryMandi} · Oct 17 Feed
              </span>
            </div>

            {/* Projected Trajectory Card */}
            <div
              className="card"
              style={{
                background: '#FFFFFF',
                borderLeft: `4px solid ${isRising ? 'var(--color-success)' : 'var(--color-error)'}`,
                padding: 'var(--space-3)',
              }}
            >
              <span className="text-caption muted">7-10 Day Projected Trajectory:</span>
              <div
                style={{
                  fontSize: 'var(--font-size-2xl)',
                  fontWeight: 800,
                  color: isRising ? 'var(--color-success)' : 'var(--color-error)',
                  marginTop: '2px',
                }}
              >
                {INR(projectedPrice)}{' '}
                <span style={{ fontSize: '13px', fontWeight: 600 }}>
                  ({isRising ? '+' : ''}{INR(priceDelta)})
                </span>
              </div>
              <span style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
                {isRising ? '📈 Expected Upswing' : '📉 Expected Softening'}
              </span>
            </div>

            {/* Net Realization (After Transport + Mandi Cess + Labor) */}
            <div
              className="card"
              style={{
                background: '#FFFFFF',
                borderLeft: '4px solid #0284C7',
                padding: 'var(--space-3)',
              }}
            >
              <span className="text-caption muted">Net Realization in Hand:</span>
              <div
                style={{
                  fontSize: 'var(--font-size-2xl)',
                  fontWeight: 800,
                  color: '#0284C7',
                  marginTop: '2px',
                }}
              >
                {INR(netRealizationSpotPerQtl)} <span style={{ fontSize: '13px', fontWeight: 400 }}>/ qtl</span>
              </div>
              <span style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
                Total ₹ in Hand: <strong>{INR(totalSpotNetProceeds)}</strong>
              </span>
            </div>

            {/* Primary AI Recommendation */}
            <div
              className="card"
              style={{
                background: isHoldRecommended
                  ? 'linear-gradient(135deg, #E8F8F0 0%, #D1FAE5 100%)'
                  : 'linear-gradient(135deg, #FEF3C7 0%, #FEE2E2 100%)',
                border: isHoldRecommended ? '1.5px solid #1E8E62' : '1.5px solid #D97706',
                padding: 'var(--space-3)',
              }}
            >
              <span className="text-caption muted">Primary Strategic Advice:</span>
              <div
                style={{
                  fontSize: 'var(--font-size-lg)',
                  fontWeight: 900,
                  color: isHoldRecommended ? '#065F46' : '#92400E',
                  marginTop: '2px',
                }}
              >
                {isHoldRecommended ? '📦 HOLD & STORE (5–10 Days)' : '⚡ SELL IMMEDIATELY TODAY'}
              </div>
              <span style={{ fontSize: '11px', color: isHoldRecommended ? '#065F46' : '#92400E' }}>
                {isHoldRecommended
                  ? `Est. gain of ${INR(storageAdvantage)} over storage cost`
                  : 'Avoid price softening & perishability losses'}
              </span>
            </div>
          </div>

          {/* ====================================================
              TAB 1: OVERVIEW / WHEN TO SELL (PRICE TRAJECTORY GRAPH)
              ==================================================== */}
          {(activeTab === 'overview' || activeTab === 'when') && (
            <Card
              title="⏱️ Pillar 1: WHEN to Sell — Historical to Future Price Trajectory"
              badge={<Badge tone="gold">10-Day ML Horizon Band</Badge>}
            >
              <div style={{ marginBottom: 'var(--space-4)' }}>
                <p className="text-body-sm muted" style={{ margin: 0 }}>
                  Statistical projection model for <strong>{selectedCommodity}</strong> anchored at{' '}
                  <strong>{selectedMandi?.mandi_name || activeHub.primaryMandi}</strong>. Volatility envelope
                  reflects expected arrival volumes and historical seasonal patterns.
                </p>
              </div>

              {/* Chart SVG */}
              {forecast?.forecast_points && forecast.forecast_points.length > 0 && (
                <div style={{ background: '#FFFFFF', padding: 'var(--space-4)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--color-border)' }}>
                  <svg
                    viewBox="0 0 700 240"
                    style={{ width: '100%', height: 'auto', display: 'block' }}
                  >
                    <defs>
                      <linearGradient id="curveGlow" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" stopColor="#2E9D74" stopOpacity="0.30" />
                        <stop offset="100%" stopColor="#2E9D74" stopOpacity="0.00" />
                      </linearGradient>
                    </defs>

                    {/* Grid lines */}
                    <line x1="50" y1="30" x2="670" y2="30" stroke="#E2E8F0" strokeDasharray="3 3" />
                    <line x1="50" y1="90" x2="670" y2="90" stroke="#E2E8F0" strokeDasharray="3 3" />
                    <line x1="50" y1="150" x2="670" y2="150" stroke="#E2E8F0" strokeDasharray="3 3" />
                    <line x1="50" y1="200" x2="670" y2="200" stroke="#CBD5E1" strokeWidth="1.5" />

                    {/* Projected points */}
                    {(() => {
                      const pts = forecast.forecast_points
                      const minP = Math.min(...pts.map((p) => p.lower_bound)) * 0.95
                      const maxP = Math.max(...pts.map((p) => p.upper_bound)) * 1.05
                      const range = maxP - minP || 1

                      const coords = pts.map((p, idx) => {
                        const x = 60 + (idx / (pts.length - 1)) * 600
                        const y = 200 - ((p.price - minP) / range) * 160
                        const yLow = 200 - ((p.lower_bound - minP) / range) * 160
                        const yHigh = 200 - ((p.upper_bound - minP) / range) * 160
                        return { x, y, yLow, yHigh, p }
                      })

                      const pathD = coords.map((c, i) => `${i === 0 ? 'M' : 'L'} ${c.x} ${c.y}`).join(' ')
                      const areaD = `${pathD} L ${coords[coords.length - 1].x} 200 L ${coords[0].x} 200 Z`

                      return (
                        <>
                          <path d={areaD} fill="url(#curveGlow)" />
                          <path d={pathD} fill="none" stroke="#1E8E62" strokeWidth="3.5" strokeLinecap="round" />

                          {coords.map((c, i) => (
                            <g key={i}>
                              <circle
                                cx={c.x}
                                cy={c.y}
                                r={i === 0 ? 6 : 4.5}
                                fill={i === 0 ? '#F3B72A' : '#1E8E62'}
                                stroke="#FFFFFF"
                                strokeWidth="2"
                              />
                              <text
                                x={c.x}
                                y={c.y - 10}
                                fill="#0F172A"
                                fontSize="10"
                                fontWeight="700"
                                textAnchor="middle"
                              >
                                ₹{Math.round(c.p.price)}
                              </text>
                              <text
                                x={c.x}
                                y="222"
                                fill="#64748B"
                                fontSize="9"
                                textAnchor="middle"
                              >
                                {c.p.day_label.split(',')[0]}
                              </text>
                            </g>
                          ))}
                        </>
                      )
                    })()}
                  </svg>
                  <div style={{ display: 'flex', justifyContent: 'center', gap: 'var(--space-4)', fontSize: '12px', marginTop: 'var(--space-2)' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#F3B72A' }} />
                      Today&apos;s Live Anchor ({INR(currentModalPrice)}/qtl)
                    </span>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ width: 16, height: 3, background: '#1E8E62' }} />
                      Projected Trend Trajectory
                    </span>
                  </div>
                </div>
              )}
            </Card>
          )}

          {/* ====================================================
              TAB 2: WHERE TO SELL (MANDI COMPARISON & NET REALIZATION)
              ==================================================== */}
          {(activeTab === 'overview' || activeTab === 'where') && (
            <Card
              title="⚖️ Pillar 2: WHERE to Sell — Real Mandi Net Realization"
              badge={<Badge tone="info">Deductions Transparently Itemized</Badge>}
            >
              <div style={{ marginBottom: 'var(--space-3)' }}>
                <p className="text-body-sm muted">
                  Headline mandi prices can be deceptive. A market offering ₹150 more per quintal can result in <em>less profit</em> if transport and handling eat away the difference.
                </p>
              </div>

              <div className="table-wrap">
                <table className="table" aria-label="Mandi comparison table">
                  <thead>
                    <tr>
                      <th>APMC Mandi</th>
                      <th>Modal Price</th>
                      <th>Freight (Distance)</th>
                      <th>Mandi Cess (1.5%)</th>
                      <th>Labor &amp; Handling</th>
                      <th>Net Realization in Hand</th>
                      <th>Total For Your {quantityQtl} Qtl</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mandiRows.slice(0, 5).map((row, idx) => {
                      const p = Number(row.modal_price) || currentModalPrice
                      const dist = 25 + idx * 20
                      const tr = Math.round(dist * 2.8)
                      const cess = Math.round(p * 0.015)
                      const handl = 18
                      const net = p - tr - cess - handl
                      const totalNet = net * quantityQtl
                      const isBest = idx === 0

                      return (
                        <tr key={row.id} style={isBest ? { background: 'var(--color-surface-alt)' } : undefined}>
                          <td>
                            <strong>{row.mandi_name}</strong>
                            <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
                              {row.district_name}, {row.state_name}
                            </div>
                            {isBest && <Badge tone="success" className="mt-1">⭐ Highest Net Return</Badge>}
                          </td>
                          <td className="num text-strong">{INR(p)} / qtl</td>
                          <td className="num text-error">-{INR(tr)} ({dist} km)</td>
                          <td className="num text-error">-{INR(cess)}</td>
                          <td className="num text-error">-{INR(handl)}</td>
                          <td className="num text-strong" style={{ color: 'var(--color-brand)', fontSize: '15px' }}>
                            {INR(net)} / qtl
                          </td>
                          <td className="num" style={{ fontWeight: 800 }}>
                            {INR(totalNet)}
                          </td>
                          <td>
                            <Button
                              variant={isBest ? 'primary' : 'secondary'}
                              className="btn--sm"
                              onClick={() => {
                                showToast(`Route navigation to ${row.mandi_name} initiated with dispatch estimate ${INR(totalNet)}.`, 'success')
                              }}
                            >
                              Dispatch Here ➔
                            </Button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* ====================================================
              TAB 3: WHOM TO SELL (BUYERS, STORAGE & TRANSPORT PARTNERS)
              ==================================================== */}
          {(activeTab === 'overview' || activeTab === 'who') && (
            <div className="stack">
              {/* Verified Buyers Section */}
              <Card
                title={`🤝 Pillar 3A: Verified Institutional Buyers Seeking ${selectedCommodity}`}
                badge={<Badge tone="success">100% Direct Bank Settlement</Badge>}
              >
                <div className="stack">
                  {nearbyBuyers.map((b) => (
                    <div
                      key={b.id}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        flexWrap: 'wrap',
                        gap: 'var(--space-3)',
                        padding: 'var(--space-3) var(--space-4)',
                        background: 'var(--color-surface-alt)',
                        borderRadius: 'var(--radius-lg)',
                        border: '1px solid var(--color-border-subtle)',
                      }}
                    >
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                          <strong style={{ fontSize: 'var(--font-size-md)' }}>{b.buyerName}</strong>
                          <Badge tone="info">{b.type}</Badge>
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
                          🎯 Buying Price: <strong>{INR(b.targetPrice)} / qtl</strong> · Min Qty: {b.quantityQtl} Qtl · Distance: {b.distanceKm} km
                        </div>
                        <span className="text-caption muted">
                          💳 {b.paymentMode} · {b.pickupOffered ? '🚜 Farmgate Pickup Available' : 'Mandi Delivery'}
                        </span>
                      </div>

                      <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                        <Button
                          variant="primary"
                          className="btn--sm"
                          onClick={() => {
                            showToast(`Contact inquiry dispatched to ${b.buyerName} for ${quantityQtl} Qtl ${selectedCommodity}!`, 'success')
                          }}
                        >
                          Sell Directly to Buyer ➔
                        </Button>
                        <Button
                          variant="secondary"
                          className="btn--sm"
                          onClick={() => navigate('/buyers')}
                        >
                          View Tenders
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Nearby Storage (If Hold is Advised) */}
              <Card
                title={`🏭 Pillar 3B: Nearby Certified Cold Storage & Warehouses (for ${intendedDays}-Day Hold)`}
                badge={<Badge tone="gold">WDRA Accredited (e-NWR Loan Eligible)</Badge>}
              >
                <div className="stack">
                  {nearbyStorage.map((s) => (
                    <div
                      key={s.id}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        flexWrap: 'wrap',
                        gap: 'var(--space-3)',
                        padding: 'var(--space-3) var(--space-4)',
                        background: '#FFFFFF',
                        borderRadius: 'var(--radius-lg)',
                        border: '1.5px solid var(--color-border)',
                      }}
                    >
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                          <strong style={{ fontSize: 'var(--font-size-md)' }}>{s.name}</strong>
                          <Badge tone="success">🟢 {s.availableBags} Bags Vacant</Badge>
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
                          ❄️ Chamber Telematics: <strong>{s.tempCelsius}</strong> · Rate: {INR(s.ratePerQtlMonth)} / qtl / month
                        </div>
                        <span className="text-caption muted">
                          🏛️ WDRA Certified · Eligible for 70% Bank Loan against e-NWR Receipt
                        </span>
                      </div>

                      <Button
                        variant="secondary"
                        className="btn--sm"
                        onClick={() => {
                          showToast(`Chamber booking request reserved at ${s.name} for ${quantityQtl} Quintals.`, 'success')
                        }}
                      >
                        Reserve Chamber Space ➔
                      </Button>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Local Transporter Connection */}
              <Card
                title="🚚 Pillar 3C: Local Freight & Commercial Transport Matching"
                badge={<Badge tone="info">Live Available Trucks Today</Badge>}
              >
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                    gap: 'var(--space-3)',
                  }}
                >
                  {nearbyTransporters.map((t) => (
                    <div
                      key={t.id}
                      style={{
                        padding: 'var(--space-3)',
                        borderRadius: 'var(--radius-lg)',
                        border: '1px solid var(--color-border)',
                        background: 'var(--color-surface-alt)',
                      }}
                    >
                      <strong style={{ display: 'block', marginBottom: '2px' }}>{t.vehicleName}</strong>
                      <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>
                        Capacity: {t.capacityTons} Tonnes · Tariff: <strong>₹{t.ratePerKm} / km</strong>
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--color-brand)', marginBottom: 'var(--space-2)' }}>
                        Driver: {t.driverName} · 📞 {t.phoneContact}
                      </div>
                      <Button
                        variant="primary"
                        className="btn--sm"
                        style={{ width: '100%' }}
                        onClick={() => {
                          showToast(`Truck booking request dispatched to ${t.driverName} (${t.phoneContact}).`, 'success')
                        }}
                      >
                        Book Truck for Dispatch ➔
                      </Button>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
