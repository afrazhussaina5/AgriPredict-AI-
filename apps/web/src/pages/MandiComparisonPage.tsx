import { useCallback, useEffect, useMemo, useId, useState } from 'react'
import {
  fetchMarketPrices,
  fetchCommodities,
  type MarketPriceRow,
  type Commodity,
} from '../api/client'
import { Badge, Button, Card } from '../components/ui'
import { LoadingState, ErrorState } from '../components/states'
import { useToast } from '../components/Toast'
import { useTranslation } from '../i18n/useTranslation'
import { navigate } from '../router'
import { useLocationContext } from '../context/LocationContext'

/* ──────────────────────────────────────────────────────────────────
   Mandi Comparison Page — Real Data Edition
   ─ Prices come from /api/v1/market/prices (real Agmarknet snapshot)
   ─ Freight / cess / loading are standard estimates, clearly labeled
   ─ ML forecast comes from /api/v1/market/forecast
   ─ All ₹ amounts are formatted; no fake static numbers
   ────────────────────────────────────────────────────────────────── */

const INR = (n: number) =>
  '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 0 })

/* Default cess / loading rates per commodity when not in API data */
const DEFAULT_CESS = 1.0   // %
const DEFAULT_LOADING = 18  // ₹/qtl

type ComputedMandi = {
  id: string
  name: string
  district: string
  state: string
  grade: string
  modalPricePerQtl: number
  cessRatePercent: number
  loadingPerQtl: number
  /** distance is not in API data; user sets a global estimate */
  transportPerQtl: number
  totalTransport: number
  cessPerQtl: number
  grossRevenue: number
  totalFees: number
  storageCost: number
  totalDeductions: number
  totalNetRevenue: number
  netRealizationPerQtl: number
  isBest: boolean
  isNearest: boolean
  netPct: number    // net / gross × 100 for the bar
  transportPct: number
  feesPct: number
  storagePct: number
  diffVsBest: number
}

type ForecastResult = {
  estimated_price: number
  lower_bound: number
  upper_bound: number
  unit: string
  model_version: string
  limitations: string[]
  disclaimer?: string
} | null

type LoadState<T> = { status: 'loading' } | { status: 'ready'; data: T } | { status: 'error' }

export function MandiComparisonPage() {
  const { t } = useTranslation()
  const { showToast } = useToast()
  const { activeHub } = useLocationContext()
  const cropId = useId()
  const qtyId = useId()
  const distanceId = useId()

  // ── UI state
  const [quantityQtl, setQuantityQtl] = useState<number>(40)
  const [freightRatePerTonneKm, setFreightRatePerTonneKm] = useState<number>(3.8)
  const [assumedDistanceKm, setAssumedDistanceKm] = useState<number>(40)
  const [holdingDays, setHoldingDays] = useState<number>(0)
  const storageRatePerQtlDay = 1.2

  // ── Data state
  const [commodities, setCommodities] = useState<LoadState<Commodity[]>>({ status: 'loading' })
  const [selectedCommodityId, setSelectedCommodityId] = useState<number | null>(null)
  const [selectedCommodityName, setSelectedCommodityName] = useState<string>('')
  const [priceRows, setPriceRows] = useState<LoadState<MarketPriceRow[]>>({ status: 'loading' })
  const [forecast, setForecast] = useState<LoadState<ForecastResult>>({ status: 'loading' })

  // ── Load commodities on mount, default to activeHub dominant crop
  useEffect(() => {
    fetchCommodities()
      .then((data) => {
        setCommodities({ status: 'ready', data })
        const matched =
          data.find((c) => c.name.toLowerCase().includes(activeHub.dominantCrop.toLowerCase())) ??
          data.find((c) => c.name.toLowerCase().includes('onion')) ??
          data[0]
        if (matched) {
          setSelectedCommodityId(matched.id)
          setSelectedCommodityName(matched.name)
        }
      })
      .catch(() => setCommodities({ status: 'error' }))
  }, [activeHub.dominantCrop])

  // ── Load real prices whenever commodity changes
  const loadPrices = useCallback(async (commodityId: number) => {
    setPriceRows({ status: 'loading' })
    setForecast({ status: 'loading' })
    try {
      const rows = await fetchMarketPrices({ commodity_id: commodityId })
      setPriceRows({ status: 'ready', data: rows })
    } catch {
      setPriceRows({ status: 'error' })
      setForecast({ status: 'ready', data: null })
    }
  }, [])

  useEffect(() => {
    if (selectedCommodityId !== null) {
      void loadPrices(selectedCommodityId)
    }
  }, [selectedCommodityId, loadPrices])

  // ── Load ML forecast when prices are ready
  useEffect(() => {
    if (priceRows.status !== 'ready' || priceRows.data.length === 0 || !selectedCommodityName) {
      if (priceRows.status === 'ready' && priceRows.data.length === 0) {
        setForecast({ status: 'ready', data: null })
      }
      return
    }
    // Prioritize active location mandi context for the forecast call
    const sample =
      priceRows.data.find(
        (r) => r.district_name?.toLowerCase() === activeHub.district.toLowerCase(),
      ) || priceRows.data[0]
    const params = new URLSearchParams({
      commodity: selectedCommodityName,
      grade: sample.grade ?? 'FAQ',
      state: sample.state_name,
      district: sample.district_name,
      market: sample.mandi_name,
    })
    fetch(`/api/v1/market/forecast?${params.toString()}`)
      .then((r) => r.json())
      .then((data: ForecastResult) => setForecast({ status: 'ready', data }))
      .catch(() => setForecast({ status: 'ready', data: null }))
  }, [priceRows, selectedCommodityName, activeHub.district])

  // ── Aggregate: up to 8 mandis with highest modal prices for this commodity
  const computedMandis: ComputedMandi[] = useMemo(() => {
    if (priceRows.status !== 'ready') return []
    const rows = priceRows.data

    // Dedupe by mandi name, keep the highest modal_price per mandi
    const mandiMap = new Map<string, MarketPriceRow>()
    for (const row of rows) {
      if (!row.modal_price) continue
      const key = `${row.mandi_name}||${row.district_name}`
      const existing = mandiMap.get(key)
      if (!existing || Number(row.modal_price) > Number(existing.modal_price ?? 0)) {
        mandiMap.set(key, row)
      }
    }

    // Sort by modal price desc, take top 8
    const top = [...mandiMap.values()]
      .sort((a, b) => Number(b.modal_price ?? 0) - Number(a.modal_price ?? 0))
      .slice(0, 8)

    if (top.length === 0) return []

    const transportPerQtl = Math.round(assumedDistanceKm * freightRatePerTonneKm * 0.1)
    const totalTransport = transportPerQtl * quantityQtl
    const storageCost = Math.round(holdingDays * storageRatePerQtlDay * quantityQtl)

    const list = top.map((row, idx) => {
      const modalPricePerQtl = Math.round(Number(row.modal_price))
      const grossRevenue = modalPricePerQtl * quantityQtl
      const cessPerQtl = Math.round((modalPricePerQtl * DEFAULT_CESS) / 100)
      const loadingPerQtl = DEFAULT_LOADING
      const totalFees = (cessPerQtl + loadingPerQtl) * quantityQtl
      const totalDeductions = totalTransport + totalFees + storageCost
      const totalNetRevenue = grossRevenue - totalDeductions
      const netRealizationPerQtl = Math.round(totalNetRevenue / (quantityQtl || 1))
      const netPct = Math.max(0, Math.round((totalNetRevenue / grossRevenue) * 100))
      const transportPct = Math.round((totalTransport / grossRevenue) * 100)
      const feesPct = Math.round((totalFees / grossRevenue) * 100)
      const storagePct = Math.round(((storageCost) / grossRevenue) * 100)

      return {
        id: `m-${idx}`,
        name: row.mandi_name,
        district: row.district_name,
        state: row.state_name,
        grade: row.grade,
        modalPricePerQtl,
        cessRatePercent: DEFAULT_CESS,
        loadingPerQtl,
        transportPerQtl,
        totalTransport,
        cessPerQtl,
        grossRevenue,
        totalFees,
        storageCost,
        totalDeductions,
        totalNetRevenue,
        netRealizationPerQtl,
        isBest: false,
        isNearest: false,
        netPct,
        transportPct,
        feesPct,
        storagePct,
        diffVsBest: 0,
      }
    })

    // Mark best net realization
    const bestIdx = list.reduce((bi, m, i) => (m.netRealizationPerQtl > list[bi].netRealizationPerQtl ? i : bi), 0)
    list[bestIdx].isBest = true

    // Mark nearest (lowest price proxy — or just flag index 0 of sorted-by-distance)
    // Since we don't have distance in API, mark the one with lowest price as "nearest" equivalent
    const lowestPriceIdx = list.reduce((li, m, i) => (m.modalPricePerQtl < list[li].modalPricePerQtl ? i : li), 0)
    if (lowestPriceIdx !== bestIdx) list[lowestPriceIdx].isNearest = true

    // Diff vs best
    const bestNet = list[bestIdx].netRealizationPerQtl
    for (const m of list) {
      m.diffVsBest = m.netRealizationPerQtl - bestNet
    }

    return list
  }, [priceRows, quantityQtl, freightRatePerTonneKm, assumedDistanceKm, holdingDays])

  const bestMandi = computedMandis.find((m) => m.isBest)

  function handleCommodityChange(id: number, name: string) {
    setSelectedCommodityId(id)
    setSelectedCommodityName(name)
  }

  const dataDate = priceRows.status === 'ready' && priceRows.data.length > 0
    ? priceRows.data[0].market_date
    : null

  return (
    <div className="container anim-fade-in">
      <div className="page-header mb-6">
        <div className="flex-between flex-wrap flex-gap-2">
          <div>
            <h1 className="text-title-lg">{t('compare.title')}</h1>
            <p className="text-body-md muted mt-1">{t('compare.subtitle')}</p>
          </div>
          {dataDate && (
            <Badge tone="info">
              📅 Agmarknet data: {new Date(dataDate).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
            </Badge>
          )}
        </div>
      </div>

      {/* ── Controls ── */}
      <Card title="🌾 Select Crop & Quantity" accent>
        <div className="card-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 'var(--space-4)' }}>
          {/* Commodity picker */}
          <div className="field">
            <label htmlFor={cropId} className="field__label">{t('compare.crop')}</label>
            {commodities.status === 'loading' && <p className="muted" style={{ fontSize: 'var(--font-size-sm)' }}>Loading crops…</p>}
            {commodities.status === 'error' && <p className="text-error" style={{ fontSize: 'var(--font-size-sm)' }}>Could not load crops</p>}
            {commodities.status === 'ready' && (
              <select
                id={cropId}
                className="field__select"
                value={selectedCommodityId ?? ''}
                onChange={(e) => {
                  const id = Number(e.target.value)
                  const com = commodities.data.find((c) => c.id === id)
                  if (com) handleCommodityChange(com.id, com.name)
                }}
              >
                {commodities.data.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            )}
          </div>

          {/* Quantity */}
          <div className="field">
            <label htmlFor={qtyId} className="field__label">
              {t('compare.quantity')}: <strong className="num">{quantityQtl} qtl</strong>
            </label>
            <input
              id={qtyId}
              type="range" min="5" max="200" step="5"
              className="range-slider"
              value={quantityQtl}
              onChange={(e) => setQuantityQtl(Number(e.target.value))}
            />
            <span className="field__hint">1 quintal = 100 kg</span>
          </div>

          {/* Estimated distance */}
          <div className="field">
            <label htmlFor={distanceId} className="field__label">
              Estimated distance: <strong className="num">{assumedDistanceKm} km</strong>
            </label>
            <input
              id={distanceId}
              type="range" min="5" max="300" step="5"
              className="range-slider"
              value={assumedDistanceKm}
              onChange={(e) => setAssumedDistanceKm(Number(e.target.value))}
            />
            <span className="field__hint">Average distance to mandi</span>
          </div>
        </div>
      </Card>

      {/* ── Best Mandi Banner ── */}
      {priceRows.status === 'ready' && bestMandi && (
        <div
          className="anim-slide-up"
          style={{
            background: 'linear-gradient(135deg, var(--color-brand-strong) 0%, var(--color-brand) 100%)',
            borderRadius: 'var(--radius-xl)',
            padding: 'var(--space-5) var(--space-6)',
            marginBottom: 'var(--space-5)',
            color: '#fff',
            display: 'flex',
            flexWrap: 'wrap',
            gap: 'var(--space-4)',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <p style={{ opacity: 0.8, fontSize: 'var(--font-size-xs)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 'var(--space-1)' }}>
              🏆 Best Net Realization — {selectedCommodityName}
            </p>
            <p style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700, margin: 0 }}>
              {bestMandi.name}
            </p>
            <p style={{ opacity: 0.8, fontSize: 'var(--font-size-sm)', margin: '2px 0 0' }}>
              {bestMandi.district}, {bestMandi.state}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-5)', flexWrap: 'wrap' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 'var(--font-size-xs)', opacity: 0.75 }}>Mandi Price</div>
              <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 700, fontFamily: 'var(--font-mono-nums)' }}>
                {INR(bestMandi.modalPricePerQtl)}/qtl
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 'var(--font-size-xs)', opacity: 0.75 }}>Net Realization</div>
              <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 700, fontFamily: 'var(--font-mono-nums)', color: '#E9B949' }}>
                {INR(bestMandi.netRealizationPerQtl)}/qtl
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 'var(--font-size-xs)', opacity: 0.75 }}>Total Net ({quantityQtl} qtl)</div>
              <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 700, fontFamily: 'var(--font-mono-nums)', color: '#E9B949' }}>
                {INR(bestMandi.totalNetRevenue)}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Price Data States ── */}
      {priceRows.status === 'loading' && (
        <Card>
          <LoadingState />
          <p className="text-center muted mt-2" style={{ fontSize: 'var(--font-size-sm)' }}>
            Fetching real Agmarknet prices…
          </p>
        </Card>
      )}
      {priceRows.status === 'error' && (
        <ErrorState
          title="Could not load prices"
          body="Check that the backend is running and try again."
          onRetry={() => selectedCommodityId && void loadPrices(selectedCommodityId)}
        />
      )}

      {/* ── Comparison Table ── */}
      {priceRows.status === 'ready' && computedMandis.length === 0 && (
        <Card>
          <p className="text-center muted" style={{ padding: 'var(--space-6) 0' }}>
            No price data available for <strong>{selectedCommodityName}</strong> in the current snapshot.
            <br />Select a different crop or check back after the next data import.
          </p>
        </Card>
      )}

      {priceRows.status === 'ready' && computedMandis.length > 0 && (
        <Card
          title={`${t('compare.title')}: ${selectedCommodityName}`}
          badge={
            <Badge tone="success">
              {computedMandis.length} mandis · Real prices
            </Badge>
          }
        >
          {/* Data freshness disclaimer */}
          <p
            style={{
              fontSize: 'var(--font-size-xs)',
              color: 'var(--color-text-muted)',
              background: 'var(--color-surface-alt)',
              borderRadius: 'var(--radius-md)',
              padding: 'var(--space-2) var(--space-3)',
              marginBottom: 'var(--space-4)',
              display: 'flex',
              gap: 'var(--space-2)',
              alignItems: 'flex-start',
            }}
          >
            <span>ℹ️</span>
            <span>
              Prices from Agmarknet official snapshot ({dataDate ?? '—'}).
              Transport ({INR(assumedDistanceKm * freightRatePerTonneKm * 0.1 * 100) }/qtl) and mandi fees are standard estimates — verify with your actual APMC before deciding.
              Cess rate: {DEFAULT_CESS}% · Loading: ₹{DEFAULT_LOADING}/qtl.
            </span>
          </p>

          <div className="table-wrap">
            <table className="table" aria-label="Mandi comparison table">
              <thead>
                <tr>
                  <th style={{ minWidth: 160 }}>{t('compare.mandiName')}</th>
                  <th>{t('compare.spotPrice')}</th>
                  <th>Transport</th>
                  <th>Fees</th>
                  {holdingDays > 0 && <th>Storage</th>}
                  <th style={{ color: 'var(--color-brand)' }}>{t('compare.netPerQuintal')}</th>
                  <th>{t('compare.totalNet')}</th>
                  <th>Realization</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {computedMandis.map((m) => (
                  <tr
                    key={m.id}
                    style={
                      m.isBest
                        ? {
                            backgroundColor: 'var(--color-surface-alt)',
                            boxShadow: 'inset 3px 0 0 var(--color-brand)',
                          }
                        : undefined
                    }
                  >
                    <td>
                      <div>
                        <strong style={{ fontSize: 'var(--font-size-sm)' }}>{m.name}</strong>
                        <div className="text-caption muted">{m.district}, {m.state}</div>
                        {m.grade && m.grade !== 'UNKNOWN' && (
                          <div className="text-caption" style={{ color: 'var(--color-brand)' }}>
                            Grade: {m.grade}
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="num" style={{ fontWeight: 600 }}>
                      {INR(m.modalPricePerQtl)}
                    </td>
                    <td className="num" style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
                      -{INR(m.transportPerQtl)}/qtl
                      <div className="text-caption muted">({INR(m.totalTransport)} total)</div>
                    </td>
                    <td className="num" style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
                      -{INR(m.cessPerQtl + m.loadingPerQtl)}/qtl
                    </td>
                    {holdingDays > 0 && (
                      <td className="num" style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
                        -{INR(m.storageCost)}
                      </td>
                    )}
                    <td
                      className="num"
                      style={{
                        fontWeight: 700,
                        fontSize: 'var(--font-size-md)',
                        color: m.isBest ? 'var(--color-brand)' : 'var(--color-text)',
                      }}
                    >
                      {INR(m.netRealizationPerQtl)}
                    </td>
                    <td className="num" style={{ fontWeight: 700, fontSize: 'var(--font-size-md)' }}>
                      {INR(m.totalNetRevenue)}
                    </td>
                    {/* Visual realization bar */}
                    <td style={{ minWidth: 100 }}>
                      <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginBottom: 2 }}>
                        {m.netPct}% net
                      </div>
                      <div className="realization-bar" style={{ width: 90 }}>
                        <div
                          className="realization-bar__net"
                          style={{ width: `${m.netPct}%` }}
                          title={`Net: ${m.netPct}%`}
                        />
                        <div
                          className="realization-bar__transport"
                          style={{ width: `${m.transportPct}%` }}
                          title={`Transport: ${m.transportPct}%`}
                        />
                        <div
                          className="realization-bar__fees"
                          style={{ width: `${m.feesPct + m.storagePct}%` }}
                          title={`Fees+Storage: ${m.feesPct + m.storagePct}%`}
                        />
                      </div>
                    </td>
                    <td>
                      {m.isBest && <Badge tone="success">{t('compare.bestMandi')}</Badge>}
                      {m.isNearest && !m.isBest && <Badge tone="neutral">Lowest Price</Badge>}
                      {!m.isBest && !m.isNearest && m.diffVsBest < 0 && (
                        <span className="text-caption" style={{ color: 'var(--color-text-muted)' }}>
                          {INR(Math.abs(m.diffVsBest))} less/qtl
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* ── ML Forecast Panel ── */}
      {forecast.status === 'ready' && forecast.data && (
        <Card
          title="🤖 ML Price Benchmark"
          badge={<Badge tone="warning">Estimate · Not a quote</Badge>}
        >
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-5)', alignItems: 'flex-start' }}>
            <div style={{ flex: '1 1 220px' }}>
              <p style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginBottom: 'var(--space-2)' }}>
                Our Ridge regression model trained on {new Intl.NumberFormat('en-IN').format(17617)} Agmarknet observations estimates:
              </p>
              <div style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 800, fontFamily: 'var(--font-mono-nums)', color: 'var(--color-brand)' }}>
                {INR(Math.round(forecast.data.estimated_price))}<span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', fontWeight: 400 }}>/qtl</span>
              </div>
              <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', marginTop: 'var(--space-1)' }}>
                Range: {INR(Math.round(forecast.data.lower_bound))} – {INR(Math.round(forecast.data.upper_bound))}
              </div>
              <div style={{ marginTop: 'var(--space-2)', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                Model: {forecast.data.model_version}
              </div>
            </div>
            <div style={{ flex: '1 1 260px' }}>
              <p style={{ fontSize: 'var(--font-size-xs)', fontWeight: 600, color: 'var(--color-warning)', marginBottom: 'var(--space-2)' }}>
                ⚠️ Important limitations:
              </p>
              <ul style={{ margin: 0, paddingLeft: 'var(--space-4)', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                {forecast.data.limitations.map((lim, i) => (
                  <li key={i} style={{ marginBottom: 'var(--space-1)' }}>{lim}</li>
                ))}
              </ul>
            </div>
          </div>
        </Card>
      )}

      {/* ── Scenario Simulator ── */}
      <Card title={t('compare.whatIf')} accent>
        <div className="card-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-4)' }}>
          <div>
            <label htmlFor="freight-slider" className="field__label">
              {t('compare.dieselSlider')}: <strong className="num">₹{freightRatePerTonneKm.toFixed(1)}/tonne/km</strong>
            </label>
            <input
              id="freight-slider"
              type="range" min="2.0" max="7.0" step="0.2"
              className="range-slider"
              value={freightRatePerTonneKm}
              onChange={(e) => setFreightRatePerTonneKm(Number(e.target.value))}
            />
            <span className="field__hint">
              Diesel cost ↑ reduces net realization. Standard: ₹3.5–4.5/tonne/km.
            </span>
          </div>
          <div>
            <label htmlFor="holding-slider" className="field__label">
              {t('compare.storageSlider')}: <strong className="num">{holdingDays} days</strong>
            </label>
            <input
              id="holding-slider"
              type="range" min="0" max="30" step="1"
              className="range-slider"
              value={holdingDays}
              onChange={(e) => setHoldingDays(Number(e.target.value))}
            />
            <span className="field__hint">
              WDRA cold store: ₹{storageRatePerQtlDay}/qtl/day standard estimate.
              {holdingDays > 0 && ` Total: ${INR(Math.round(holdingDays * storageRatePerQtlDay * quantityQtl))}`}
            </span>
          </div>
        </div>
      </Card>

      {/* ── Legend ── */}
      <div
        style={{
          display: 'flex',
          gap: 'var(--space-3)',
          flexWrap: 'wrap',
          alignItems: 'center',
          marginBottom: 'var(--space-4)',
          fontSize: 'var(--font-size-xs)',
          color: 'var(--color-text-muted)',
        }}
      >
        <span style={{ fontWeight: 600 }}>Realization bar:</span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 12, height: 12, borderRadius: 2, background: 'var(--color-primary)', display: 'inline-block' }} />
          Net income
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 12, height: 12, borderRadius: 2, background: '#d97706', display: 'inline-block' }} />
          Transport
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 12, height: 12, borderRadius: 2, background: '#9ca3af', display: 'inline-block' }} />
          Mandi fees + storage
        </span>
      </div>

      {/* ── Navigation ── */}
      <div className="inline-actions" style={{ justifyContent: 'space-between' }}>
        <Button variant="secondary" onClick={() => navigate('/market')}>
          ← Back to Price Board
        </Button>
        <Button
          variant="primary"
          onClick={() => {
            showToast('Opening buyer marketplace with current crop context', 'info')
            navigate('/buyers')
          }}
        >
          Find Buyers at These Prices →
        </Button>
      </div>
    </div>
  )
}
