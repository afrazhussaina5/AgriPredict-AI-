import { useCallback, useEffect, useState } from 'react'

import {
  fetchCommodities,
  fetchMarketFreshness,
  fetchMarketGrades,
  fetchMarketPrices,
  type Commodity,
  type MarketGrade,
  type MarketPriceRow,
} from '../api/client'
import { SelectField } from '../components/fields'
import { Alert, Badge, Button } from '../components/ui'
import { EmptyState, ErrorState, LoadingState } from '../components/states'
import { useTranslation } from '../i18n/useTranslation'
import { navigate } from '../router'
import { useLocationContext } from '../context/LocationContext'

/* Premium Market Price Board — card-based mobile-first design with search,
   sort, view toggle, and mini price-range bars.
   No fake prices; null modal_price renders as "not published". */

type Loadable<T> =
  | { status: 'loading' }
  | { status: 'ready'; data: T }
  | { status: 'error' }

const LOADING: Loadable<never> = { status: 'loading' }
const INR = (n: number) => '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 0 })
const parseModal = (v: string | null): number | null => (v === null ? null : parseFloat(v))
type SortKey = 'modal_desc' | 'modal_asc' | 'name_asc' | 'arrivals_desc'

function PriceCard({ row }: { row: MarketPriceRow }) {
  const modal = parseModal(row.modal_price)
  const hasModal = modal !== null
  return (
    <div
      className="anim-slide-up"
      style={{ padding: 'var(--space-4)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--color-border-subtle)', background: 'var(--color-surface)', boxShadow: 'var(--shadow-card)', transition: 'box-shadow var(--transition-fast), border-color var(--transition-fast)', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}
    >
      {/* Commodity + Grade */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 'var(--font-size-md)', color: 'var(--color-text-strong)' }}>
            {row.commodity_name}
          </div>
          <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginTop: '2px' }}>
            {row.mandi_name} · {row.district_name}
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '3px' }}>
          <Badge tone={row.grade === 'UNKNOWN' ? 'neutral' : 'info'}>
            {row.grade === 'UNKNOWN' ? 'Ungraded' : row.grade}
          </Badge>
          {row.state_name && (
            <span style={{ fontSize: '10px', color: 'var(--color-text-muted)' }}>{row.state_name}</span>
          )}
        </div>
      </div>

      {/* Price */}
      <div style={{ background: hasModal ? 'var(--color-surface-alt)' : 'var(--color-surface-muted)', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-3)' }}>
        {hasModal ? (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>Modal Price</span>
              <span className="num" style={{ fontSize: 'var(--font-size-xl)', fontWeight: 800, color: 'var(--color-brand-strong)' }}>
                {INR(modal!)}
                <span style={{ fontSize: '11px', fontWeight: 400, color: 'var(--color-text-secondary)' }}>/{row.unit_code}</span>
              </span>
            </div>
          </>
        ) : (
          <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)', fontStyle: 'italic' }}>Price not published</span>
        )}
      </div>

      {/* Footer */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '11px' }}>
        <span style={{ color: 'var(--color-text-muted)' }}>
          📅 {row.market_date}
          {row.arrivals ? <> · 📦 {row.arrivals} {row.unit_code}</> : ''}
        </span>
        <span style={{ background: 'var(--color-surface-muted)', color: 'var(--color-text-muted)', padding: '2px 6px', borderRadius: 'var(--radius-sm)', fontSize: '10px' }}>
          {row.source_name}
        </span>
      </div>
    </div>
  )
}

export function MarketPage() {
  const { t, locale } = useTranslation()
  const { activeHub } = useLocationContext()

  const [rows, setRows] = useState<Loadable<MarketPriceRow[]>>(LOADING)
  const [freshness, setFreshness] = useState<{ last_imported_at: string | null } | null>(null)
  const [freshnessMissing, setFreshnessMissing] = useState(false)
  const [commodities, setCommodities] = useState<Loadable<Commodity[]>>(LOADING)
  const [grades, setGrades] = useState<Loadable<MarketGrade[]>>(LOADING)

  const [commodityId, setCommodityId] = useState<number | null>(null)
  const [gradeId, setGradeId] = useState<number | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('modal_desc')
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('cards')

  const loadRows = useCallback(async (commodity: number | null, grade: number | null) => {
    setRows(LOADING)
    try {
      const params: { commodity_id?: number; grade_id?: number } = {}
      if (commodity !== null) params.commodity_id = commodity
      if (grade !== null) params.grade_id = grade
      setRows({ status: 'ready', data: await fetchMarketPrices(params) })
    } catch {
      setRows({ status: 'error' })
    }
  }, [])

  const loadFreshness = useCallback(async () => {
    try { setFreshness(await fetchMarketFreshness()); setFreshnessMissing(false) }
    catch { setFreshnessMissing(true) }
  }, [])

  const loadFilters = useCallback(async () => {
    setCommodities(LOADING); setGrades(LOADING)
    try { setCommodities({ status: 'ready', data: await fetchCommodities() }) } catch { setCommodities({ status: 'error' }) }
    try { setGrades({ status: 'ready', data: await fetchMarketGrades() }) } catch { setGrades({ status: 'error' }) }
  }, [])

  const data = rows.status === 'ready' ? rows.data : []
  const commodityRows = commodities.status === 'ready' ? commodities.data : []
  const gradeRows = grades.status === 'ready' ? grades.data : []

  const visibleGrades = commodityId === null
    ? gradeRows
    : gradeRows.filter((r) => r.commodity_id === null || r.commodity_id === commodityId)

  const effectiveGradeId = gradeId !== null && visibleGrades.some((r) => r.id === gradeId) ? gradeId : null

  useEffect(() => { void loadFreshness(); void loadFilters() }, [loadFreshness, loadFilters])
  useEffect(() => { void loadRows(commodityId, effectiveGradeId) }, [loadRows, commodityId, effectiveGradeId])

  const filteredData = data
    .filter((row) => {
      if (!searchQuery) return true
      const q = searchQuery.toLowerCase()
      return (
        row.commodity_name.toLowerCase().includes(q) ||
        row.mandi_name.toLowerCase().includes(q) ||
        (row.district_name ?? '').toLowerCase().includes(q) ||
        (row.state_name ?? '').toLowerCase().includes(q)
      )
    })
    .sort((a, b) => {
      const aP = parseModal(a.modal_price) ?? 0
      const bP = parseModal(b.modal_price) ?? 0
      switch (sortKey) {
        case 'modal_desc': return bP - aP
        case 'modal_asc': return aP - bP
        case 'name_asc': return a.commodity_name.localeCompare(b.commodity_name)
        case 'arrivals_desc': return (b.arrivals ?? 0) - (a.arrivals ?? 0)
        default: return 0
      }
    })

  const totalWithPrice = data.filter((r) => r.modal_price !== null).length
  const avgModal = totalWithPrice > 0
    ? Math.round(data.reduce((s, r) => s + (parseModal(r.modal_price) ?? 0), 0) / totalWithPrice)
    : null

  return (
    <div className="container anim-fade-in" style={{ paddingBottom: 'var(--space-10)' }}>
      {/* Header */}
      <div className="page-header">
        <div className="flex-between flex-wrap flex-gap-2">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-1)' }}>
              <Badge tone="success" className="badge--pulse"><span className="pulse-dot" /> Live Mandi Feed</Badge>
              <span className="eyebrow">APMC Market Intelligence</span>
            </div>
            <h1 className="text-title-xl" style={{ margin: 0 }}>{t('market.title')}</h1>
            <p className="text-body-md muted" style={{ margin: 'var(--space-1) 0 0' }}>{t('market.subtitle')}</p>
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
            <Button variant="secondary" onClick={() => navigate('/forecast')}>📈 10-Day Forecast</Button>
            <Button variant="primary" onClick={() => navigate('/compare')}>⚖️ Compare Mandis</Button>
          </div>
        </div>
      </div>

      <Alert tone="info" title={t('market.notice.unverified')} />

      {/* Quick Stats */}
      {rows.status === 'ready' && data.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 'var(--space-3)', margin: 'var(--space-5) 0' }}>
          {[
            { icon: '📋', value: data.length.toLocaleString('en-IN'), label: 'Total Listings' },
            { icon: '✅', value: totalWithPrice.toLocaleString('en-IN'), label: 'With Price' },
            { icon: '💰', value: avgModal ? INR(avgModal) : '—', label: 'Avg Modal Price' },
            { icon: '🕐', value: freshness?.last_imported_at ? new Date(freshness.last_imported_at).toLocaleDateString(locale) : '—', label: 'Last Updated' },
          ].map((s) => (
            <div key={s.label} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border-subtle)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-3)', textAlign: 'center' }}>
              <div style={{ fontSize: '20px', marginBottom: '4px' }}>{s.icon}</div>
              <div className="num" style={{ fontSize: 'var(--font-size-lg)', fontWeight: 700, color: 'var(--color-brand-strong)' }}>{s.value}</div>
              <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '2px' }}>{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {!freshnessMissing && freshness?.last_imported_at && (
        <p className="text-caption muted" style={{ marginBottom: 'var(--space-4)' }}>
          📡 Snapshot: {new Date(freshness.last_imported_at).toLocaleString(locale)} · {t('market.freshness.staleNote')}
        </p>
      )}

      {/* Filter Panel */}
      <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border-subtle)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)', marginBottom: 'var(--space-5)' }}>
        <div style={{ marginBottom: 'var(--space-3)' }}>
          <input
            type="search"
            className="input"
            placeholder="🔍 Search by crop name, mandi, district, or state..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: '100%' }}
          />
          <div style={{ marginTop: 'var(--space-2)', display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>Quick District Filter:</span>
            <button
              type="button"
              className={`filter-pill ${searchQuery.toLowerCase() === activeHub.district.toLowerCase() ? 'filter-pill--active' : ''}`}
              onClick={() => setSearchQuery(searchQuery.toLowerCase() === activeHub.district.toLowerCase() ? '' : activeHub.district)}
            >
              📍 {activeHub.name} ({activeHub.district})
            </button>
            <button
              type="button"
              className={`filter-pill ${searchQuery.toLowerCase() === activeHub.dominantCrop.toLowerCase() ? 'filter-pill--active' : ''}`}
              onClick={() => setSearchQuery(searchQuery.toLowerCase() === activeHub.dominantCrop.toLowerCase() ? '' : activeHub.dominantCrop)}
            >
              {activeHub.icon} {activeHub.dominantCrop}
            </button>
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 'var(--space-3)', alignItems: 'end' }}>
          <SelectField
            id="market-commodity"
            label={t('market.filter.commodity')}
            value={commodityId ?? ''}
            onChange={(e) => { setCommodityId(e.target.value ? Number(e.target.value) : null); setGradeId(null) }}
          >
            <option value="">{t('market.filter.commodityAll')}</option>
            {commodityRows.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </SelectField>

          <SelectField
            id="market-grade"
            label={t('market.filter.grade')}
            value={effectiveGradeId ?? ''}
            onChange={(e) => setGradeId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">{t('market.filter.gradeAll')}</option>
            {visibleGrades.map((r) => (
              <option key={r.id} value={r.id}>{r.commodity_code ? `${r.code} - ${r.commodity_code}` : r.code}</option>
            ))}
          </SelectField>

          <div>
            <label htmlFor="mkt-sort" style={{ display: 'block', fontSize: 'var(--font-size-xs)', fontWeight: 600, marginBottom: 'var(--space-1)', color: 'var(--color-text-secondary)' }}>Sort By</label>
            <select id="mkt-sort" className="field__select" value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)}>
              <option value="modal_desc">Price: High → Low</option>
              <option value="modal_asc">Price: Low → High</option>
              <option value="name_asc">Crop Name A–Z</option>
              <option value="arrivals_desc">Arrivals: Most</option>
            </select>
          </div>

          <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap', alignItems: 'center' }}>
            <button type="button" className={`filter-pill ${viewMode === 'cards' ? 'filter-pill--active' : ''}`} onClick={() => setViewMode('cards')}>⊞ Cards</button>
            <button type="button" className={`filter-pill ${viewMode === 'table' ? 'filter-pill--active' : ''}`} onClick={() => setViewMode('table')}>☰ Table</button>
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => { setCommodityId(null); setGradeId(null); setSearchQuery(''); setSortKey('modal_desc') }}>✕ Reset</button>
          </div>
        </div>
      </div>

      {/* Result count */}
      {rows.status === 'ready' && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
          <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
            {filteredData.length === data.length
              ? `Showing all ${data.length.toLocaleString('en-IN')} listings`
              : `Showing ${filteredData.length.toLocaleString('en-IN')} of ${data.length.toLocaleString('en-IN')} listings`}
          </span>
          {searchQuery && (
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => setSearchQuery('')}>Clear search</button>
          )}
        </div>
      )}

      {/* States */}
      {rows.status === 'loading' && <LoadingState />}
      {rows.status === 'error' && (
        <ErrorState title={t('market.error.title')} body={t('market.error.body')} onRetry={() => void loadRows(commodityId, effectiveGradeId)} />
      )}
      {rows.status === 'ready' && filteredData.length === 0 && (
        <EmptyState title={t('market.empty.title')} body={t('market.empty.body')} />
      )}

      {/* Cards Grid */}
      {rows.status === 'ready' && filteredData.length > 0 && viewMode === 'cards' && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--space-4)' }}>
            {filteredData.slice(0, 200).map((row) => (
              <PriceCard key={`${row.commodity_code}:${row.grade}:${row.mandi_code}:${row.market_date}`} row={row} />
            ))}
          </div>
          {filteredData.length > 200 && (
            <div style={{ textAlign: 'center', marginTop: 'var(--space-6)', color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>
              Showing first 200 cards.{' '}
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => setViewMode('table')}>Switch to Table view</button>{' '}
              to see all {filteredData.length.toLocaleString('en-IN')} results or refine your filters.
            </div>
          )}
        </>
      )}

      {/* Table View */}
      {rows.status === 'ready' && filteredData.length > 0 && viewMode === 'table' && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t('market.col.commodity')}</th>
                <th scope="col">{t('market.col.grade')}</th>
                <th scope="col">{t('market.col.mandi')}</th>
                <th scope="col">{t('market.col.district')}</th>
                <th scope="col">{t('market.col.date')}</th>
                <th scope="col">{t('market.col.price')}</th>
                <th scope="col">{t('market.col.arrivals')}</th>
                <th scope="col">{t('market.col.source')}</th>
              </tr>
            </thead>
            <tbody>
              {filteredData.slice(0, 500).map((row) => (
                <tr key={`${row.commodity_code}:${row.grade}:${row.mandi_code}:${row.market_date}:${row.unit_code}`}>
                  <th scope="row" style={{ fontWeight: 600 }}>{row.commodity_name}</th>
                  <td>{row.grade === 'UNKNOWN' ? <Badge tone="neutral">{t('market.notGraded')}</Badge> : <Badge tone="info">{row.grade}</Badge>}</td>
                  <td>{row.mandi_name}</td>
                  <td>{row.district_name}</td>
                  <td className="num text-secondary">{row.market_date}</td>
                  <td className="num text-strong" style={{ fontSize: 'var(--font-size-md)' }}>
                    {row.modal_price === null ? <span className="muted">{t('market.noPrice')}</span> : t('market.perUnit', { price: row.modal_price, unit: row.unit_code })}
                  </td>
                  <td className="num">{row.arrivals === null ? <span className="muted">{t('market.noArrivals')}</span> : row.arrivals}</td>
                  <td className="text-caption muted">{row.source_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
