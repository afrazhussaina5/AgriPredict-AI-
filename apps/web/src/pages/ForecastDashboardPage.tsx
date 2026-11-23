import { useCallback, useEffect, useState } from 'react'
import {
  fetchCommodities,
  fetchMarketPrices,
  fetchForecastSeries,
  type Commodity,
  type MarketPriceRow,
  type SeriesForecastResponse,
} from '../api/client'
import { WeatherWidget } from '../components/WeatherWidget'
import { Badge, Button, Card } from '../components/ui'
import { LoadingState } from '../components/states'
import { navigate } from '../router'
import { useLocationContext } from '../context/LocationContext'

const INR = (n: number) =>
  '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 0 })

export function ForecastDashboardPage() {
  const { activeHub } = useLocationContext()
  const [commodities, setCommodities] = useState<Commodity[]>([])
  const [selectedCommodity, setSelectedCommodity] = useState<string>('Onion')
  const [selectedDays, setSelectedDays] = useState<number>(10)
  const [mandiRows, setMandiRows] = useState<MarketPriceRow[]>([])
  const [selectedMandi, setSelectedMandi] = useState<MarketPriceRow | null>(null)

  const [forecast, setForecast] = useState<SeriesForecastResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  // 1. Load available commodities & default to activeHub dominant crop
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

  // 2. Fetch market mandis for selected crop and prioritize activeHub district/state
  useEffect(() => {
    if (!selectedCommodity) return
    const com = commodities.find((c) => c.name === selectedCommodity)
    const param = com ? { commodity_id: com.id } : undefined

    fetchMarketPrices(param)
      .then((rows) => {
        setMandiRows(rows)
        if (rows.length > 0) {
          const matchedMandi =
            rows.find((r) => r.district_name?.toLowerCase() === activeHub.district.toLowerCase()) ||
            rows.find((r) => r.state_name?.toLowerCase() === activeHub.state.toLowerCase()) ||
            rows[0]
          setSelectedMandi(matchedMandi)
        }
      })
      .catch(() => {})
  }, [selectedCommodity, commodities, activeHub.district, activeHub.state])

  // 3. Load 7-10 day Forecast Series from backend ML engine
  const loadForecast = useCallback(async () => {
    if (!selectedCommodity || !selectedMandi) return
    setLoading(true)
    setError(null)

    try {
      const data = await fetchForecastSeries({
        commodity: selectedCommodity,
        grade: selectedMandi.grade || 'FAQ',
        state: selectedMandi.state_name,
        district: selectedMandi.district_name,
        market: selectedMandi.mandi_name,
        days: selectedDays,
      })
      setForecast(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate forecast')
    } finally {
      setLoading(false)
    }
  }, [selectedCommodity, selectedMandi, selectedDays])

  useEffect(() => {
    if (selectedMandi) {
      void loadForecast()
    }
  }, [selectedMandi, selectedDays, loadForecast])

  // Compute graph scaling
  const points = forecast?.points ?? []
  const maxPrice = Math.max(...points.map((p) => p.upper_bound), 3000)
  const minPrice = Math.max(0, Math.min(...points.map((p) => p.lower_bound), 1000) * 0.9)
  const range = maxPrice - minPrice || 1

  const isStoreAction = forecast?.action === 'STORE'
  const isSellAction = forecast?.action === 'SELL_NOW'

  return (
    <div className="container anim-fade-in" style={{ paddingBottom: 'var(--space-8)' }}>
      {/* Header */}
      <div className="page-header mb-5">
        <div className="flex-between flex-wrap flex-gap-2">
          <div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-1)' }}>
              <Badge tone="gold" className="badge--pulse">
                <span className="pulse-dot" /> 10-Day Horizon Projection Model
              </Badge>
              <span className="eyebrow">STORE OR SELL SCENARIO ADVISOR (स्टोर करें या बेचें?)</span>
            </div>
            <h1 className="text-title-xl">7 to 10-Day Mandi Price Projection &amp; Storage Economics</h1>
            <p className="text-body-md muted mt-1">
              Statistical trajectory with daily volatility bounds and weather correlation. Explicitly compare net price gain against storage rentals: <strong>STORE</strong> only if expected gain exceeds ₹1.20/kg/month storage cost.
            </p>
          </div>
          <div className="flex-center flex-gap-2">
            <Button variant="secondary" onClick={() => navigate('/compare')}>
              ⚖️ Compare Mandis
            </Button>
            <Button variant="primary" onClick={() => navigate('/chat')}>
              🎙️ Ask AgriMitra Voice AI
            </Button>
          </div>
        </div>
      </div>

      {/* Control Panel */}
      <Card title="🎯 Select Crop, Mandi &amp; Forecast Horizon" accent>
        <div
          className="card-grid"
          style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-4)' }}
        >
          {/* Crop Selector */}
          <div className="field">
            <label htmlFor="forecast-commodity-select" className="field__label">Commodity (फसल चुनें)</label>
            <select
              id="forecast-commodity-select"
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

          {/* Mandi Selector */}
          <div className="field">
            <label htmlFor="forecast-mandi-select" className="field__label">Target Mandi (मंडी बेंचमार्क)</label>
            <select
              id="forecast-mandi-select"
              className="field__select"
              value={selectedMandi ? `${selectedMandi.mandi_code}-${selectedMandi.district_name}` : ''}
              onChange={(e) => {
                const found = mandiRows.find(
                  (m) => `${m.mandi_code}-${m.district_name}` === e.target.value,
                )
                if (found) setSelectedMandi(found)
              }}
            >
              {mandiRows.slice(0, 30).map((m, idx) => (
                <option key={`${m.mandi_code}-${idx}`} value={`${m.mandi_code}-${m.district_name}`}>
                  {m.mandi_name} ({m.district_name}, {m.state_name})
                </option>
              ))}
            </select>
          </div>

          {/* Days Horizon */}
          <div className="field">
            <span className="field__label">
              Prediction Horizon: <strong>{selectedDays} Days</strong>
            </span>
            <div className="flex-gap-2 flex" style={{ marginTop: 'var(--space-1)' }}>
              {[7, 10, 14].map((d) => (
                <button
                  key={d}
                  type="button"
                  className={`btn btn--sm ${selectedDays === d ? 'btn--primary' : 'btn--secondary'}`}
                  onClick={() => setSelectedDays(d)}
                >
                  {d} Days
                </button>
              ))}
            </div>
          </div>
        </div>
      </Card>

      {/* Location Weather & Agronomy Preservations */}
      {selectedMandi && (
        <WeatherWidget
          onLocationChange={(district, state) => {
            // Keep weather synced
            console.info(`[Weather Location] ${district}, ${state}`)
          }}
        />
      )}

      {/* Loading & Error States */}
      {loading && (
        <Card>
          <LoadingState label="Computing Neural Price Trajectory &amp; Storage Thresholds..." />
        </Card>
      )}

      {error && (
        <Card>
          <div className="text-center text-error" style={{ padding: 'var(--space-4)' }}>
            <p>⚠️ {error}</p>
            <Button variant="secondary" onClick={() => void loadForecast()}>
              Retry Forecast
            </Button>
          </div>
        </Card>
      )}

      {/* Main Forecast Dashboard UI */}
      {!loading && forecast && (
        <div className="stack anim-slide-up" style={{ gap: 'var(--space-5)' }}>
          {/* Action Recommendation Banner: STORE vs SELL */}
          <div
            style={{
              background: isStoreAction
                ? 'linear-gradient(135deg, #153F35 0%, #26745A 100%)'
                : isSellAction
                  ? 'linear-gradient(135deg, #7F1D1D 0%, #B91C1C 100%)'
                  : 'linear-gradient(135deg, #78350F 0%, #D97706 100%)',
              color: '#FFFFFF',
              borderRadius: 'var(--radius-xl)',
              padding: 'var(--space-5) var(--space-6)',
              boxShadow: 'var(--shadow-md)',
              display: 'flex',
              flexWrap: 'wrap',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 'var(--space-4)',
            }}
          >
            <div style={{ maxWidth: '38rem' }}>
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-1)' }}>
                <span
                  style={{
                    background: '#E9B949',
                    color: '#202923',
                    fontSize: 'var(--font-size-xs)',
                    fontWeight: 800,
                    padding: '2px 8px',
                    borderRadius: 'var(--radius-pill)',
                    textTransform: 'uppercase',
                  }}
                >
                  {forecast.action_title || `AI SIGNAL: ${forecast.action}`}
                </span>
                <span style={{ fontSize: 'var(--font-size-xs)', opacity: 0.9 }}>
                  {forecast.horizon_days}-Day Decision Horizon
                </span>
              </div>
              <h2 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 800, margin: 'var(--space-1) 0', color: '#FFFFFF' }}>
                {forecast.action_summary}
              </h2>
              <p style={{ margin: 0, fontSize: 'var(--font-size-sm)', opacity: 0.9 }}>
                Benchmark Market: <strong>{forecast.market}</strong> ({forecast.district}, {forecast.state}) · Quality Grade: {forecast.grade}
              </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', alignItems: 'flex-end' }}>
              <div style={{ display: 'flex', gap: 'var(--space-4)', textAlign: 'right' }}>
                <div>
                  <div style={{ fontSize: 'var(--font-size-xs)', opacity: 0.8 }}>Current Spot</div>
                  <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 800, fontFamily: 'var(--font-mono-nums)' }}>
                    {INR(forecast.base_benchmark_price)}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 'var(--font-size-xs)', opacity: 0.8 }}>Projected {forecast.horizon_days}d Price</div>
                  <div
                    style={{
                      fontSize: 'var(--font-size-xl)',
                      fontWeight: 800,
                      fontFamily: 'var(--font-mono-nums)',
                      color: forecast.price_change_projected_pct >= 0 ? '#4ADE80' : '#FCA5A5',
                    }}
                  >
                    {INR(forecast.projected_price_horizon)}
                  </div>
                </div>
              </div>

              {/* Direct Next Step Action */}
              <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-1)' }}>
                {isStoreAction ? (
                  <Button
                    variant="gold"
                    onClick={() => navigate('/services')}
                    style={{ fontWeight: 700 }}
                  >
                    🏭 Reserve Cold Storage / Godown →
                  </Button>
                ) : (
                  <Button
                    variant="primary"
                    onClick={() => navigate('/compare')}
                    style={{ fontWeight: 700, background: '#FFFFFF', color: '#B91C1C' }}
                  >
                    ⚖️ Compare Mandis to Sell Today →
                  </Button>
                )}
              </div>
            </div>
          </div>

          {/* Interactive Chart Canvas Simulation */}
          <Card
            title={`📈 ${forecast.commodity} 10-Day Price Trajectory Curve`}
            badge={
              <Badge tone="info">
                Model: {forecast.model_version}
              </Badge>
            }
          >
            {/* Visual SVG Price Trend Chart */}
            <div style={{ width: '100%', overflowX: 'auto', padding: 'var(--space-2) 0' }}>
              <div style={{ minWidth: 680, position: 'relative' }}>
                <svg viewBox="0 0 700 240" style={{ width: '100%', height: 240 }}>
                  <defs>
                    <linearGradient id="curveGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--color-primary)" stopOpacity="0.3" />
                      <stop offset="100%" stopColor="var(--color-primary)" stopOpacity="0.0" />
                    </linearGradient>
                  </defs>

                  {/* Grid Lines */}
                  {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => {
                    const y = 200 - pct * 160
                    const p = Math.round(minPrice + pct * range)
                    return (
                      <g key={i}>
                        <line x1="40" y1={y} x2="680" y2={y} stroke="var(--color-border-subtle)" strokeDasharray="3 3" />
                        <text x="35" y={y + 4} fill="var(--color-text-muted)" fontSize="10" textAnchor="end">
                          ₹{p}
                        </text>
                      </g>
                    )
                  })}

                  {/* Shaded Confidence Interval Tunnel */}
                  <polygon
                    points={[
                      ...points.map((pt, i) => {
                        const x = 50 + (i / (points.length - 1)) * 620
                        const y = 200 - ((pt.upper_bound - minPrice) / range) * 160
                        return `${x},${y}`
                      }),
                      ...[...points].reverse().map((pt, i) => {
                        const revIdx = points.length - 1 - i
                        const x = 50 + (revIdx / (points.length - 1)) * 620
                        const y = 200 - ((pt.lower_bound - minPrice) / range) * 160
                        return `${x},${y}`
                      }),
                    ].join(' ')}
                    fill="var(--color-brand-glow)"
                    opacity="0.6"
                  />

                  {/* Main Trend Line */}
                  <polyline
                    fill="none"
                    stroke="var(--color-primary)"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    points={points
                      .map((pt, i) => {
                        const x = 50 + (i / (points.length - 1)) * 620
                        const y = 200 - ((pt.price - minPrice) / range) * 160
                        return `${x},${y}`
                      })
                      .join(' ')}
                  />

                  {/* Data Points */}
                  {points.map((pt, i) => {
                    const x = 50 + (i / (points.length - 1)) * 620
                    const y = 200 - ((pt.price - minPrice) / range) * 160
                    const isToday = pt.day_label.includes('Today')

                    return (
                      <g key={i} className="chart-point">
                        <circle
                          cx={x}
                          cy={y}
                          r={isToday ? 6 : 4}
                          fill={isToday ? '#E9B949' : pt.is_historical ? 'var(--color-text-muted)' : 'var(--color-primary)'}
                          stroke="#FFFFFF"
                          strokeWidth="2"
                        />
                        {/* Day label */}
                        <text
                          x={x}
                          y={225}
                          fill={isToday ? 'var(--color-brand)' : 'var(--color-text-secondary)'}
                          fontSize="9"
                          fontWeight={isToday ? 700 : 400}
                          textAnchor="middle"
                        >
                          {pt.day_label.split(',')[0]}
                        </text>
                      </g>
                    )
                  })}
                </svg>
              </div>
            </div>

            {/* Legend */}
            <div
              style={{
                display: 'flex',
                gap: 'var(--space-4)',
                fontSize: 'var(--font-size-xs)',
                color: 'var(--color-text-muted)',
                justifyContent: 'center',
                flexWrap: 'wrap',
                marginTop: 'var(--space-3)',
                paddingTop: 'var(--space-2)',
                borderTop: '1px solid var(--color-border-subtle)',
              }}
            >
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 12, height: 3, background: 'var(--color-primary)' }} />
                Statistical Projected Modal Price
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 12, height: 12, background: 'var(--color-brand-glow)', borderRadius: 2 }} />
                Volatility Confidence Band (95% to 64%)
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 8, height: 8, background: '#E9B949', borderRadius: '50%' }} />
                Oct 17 Benchmark Anchor (Agmarknet)
              </span>
            </div>
          </Card>

          {/* Daily Granular Forecast Table */}
          <Card title="📅 Daily Price Trajectory &amp; Action Timeline">
            <div className="table-wrap">
              <table className="table" aria-label="10-day price forecast table">
                <thead>
                  <tr>
                    <th>Date / Horizon</th>
                    <th>Projected Price</th>
                    <th>Expected Range (Min – Max)</th>
                    <th>Daily Delta</th>
                    <th>Confidence</th>
                    <th>Action Signal</th>
                  </tr>
                </thead>
                <tbody>
                  {points.map((pt, idx) => {
                    const isToday = pt.day_label.includes('Today')
                    const prevPrice = idx > 0 ? points[idx - 1].price : pt.price
                    const delta = pt.price - prevPrice
                    const deltaPct = prevPrice > 0 ? Math.round((delta / prevPrice) * 1000) / 10 : 0

                    return (
                      <tr
                        key={pt.date}
                        style={
                          isToday
                            ? { background: 'var(--color-surface-alt)', fontWeight: 600 }
                            : undefined
                        }
                      >
                        <td>
                          <strong>{pt.day_label}</strong>
                          {isToday && <Badge tone="gold" className="ml-2">Live Anchor</Badge>}
                          {pt.is_historical && <span className="text-caption muted ml-2">Historical</span>}
                        </td>
                        <td className="num text-strong" style={{ fontSize: 'var(--font-size-md)', color: 'var(--color-brand)' }}>
                          {INR(pt.price)} / qtl
                        </td>
                        <td className="num text-secondary">
                          {INR(pt.lower_bound)} – {INR(pt.upper_bound)}
                        </td>
                        <td className="num">
                          {idx === 0 ? (
                            '—'
                          ) : deltaPct >= 0 ? (
                            <span style={{ color: 'var(--color-success)' }}>+{INR(delta)} (+{deltaPct}%)</span>
                          ) : (
                            <span style={{ color: 'var(--color-error)' }}>-{INR(Math.abs(delta))} ({deltaPct}%)</span>
                          )}
                        </td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                            <div className="progress-bar" style={{ width: 60, height: 6 }}>
                              <div
                                className="progress-bar__fill progress-bar__fill--success"
                                style={{ width: `${pt.confidence_pct}%` }}
                              />
                            </div>
                            <span className="text-caption num">{pt.confidence_pct}%</span>
                          </div>
                        </td>
                        <td>
                          {isToday ? (
                            <Badge tone="neutral">Current Spot</Badge>
                          ) : deltaPct > 1.0 ? (
                            <Badge tone="success">📈 Store / Hold</Badge>
                          ) : deltaPct < -1.0 ? (
                            <Badge tone="error">📉 Sell Soon</Badge>
                          ) : (
                            <Badge tone="neutral">Stable</Badge>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
