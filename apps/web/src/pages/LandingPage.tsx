import { useEffect, useState } from 'react'
import { fetchMarketPrices, type MarketPriceRow } from '../api/client'
import { HealthStatus } from '../components/HealthStatus'
import { WeatherWidget } from '../components/WeatherWidget'
import { Badge, Button } from '../components/ui'
import { useTranslation } from '../i18n/useTranslation'
import { navigate } from '../router'
import { useLocationContext } from '../context/LocationContext'
import { AgriPredictLogo } from '../components/brand/AgriPredictLogo'

type HighlightCommodity = {
  code: string
  nameEn: string
  nameHi: string
  nameTe: string
  icon: string
  benchmarkMandi: string
  modalPrice: number
  minPrice: number
  maxPrice: number
  trendPct: number
  action: 'STORE' | 'SELL_NOW' | 'WATCH'
  actionLabel: string
}

const DEFAULT_HIGHLIGHTS: HighlightCommodity[] = [
  {
    code: 'onion',
    nameEn: 'Onion',
    nameHi: 'कांदा / प्याज',
    nameTe: 'ఉల్లిపాయ',
    icon: '🧅',
    benchmarkMandi: 'Lasalgaon APMC (Nashik)',
    modalPrice: 3612,
    minPrice: 3100,
    maxPrice: 3950,
    trendPct: 8.5,
    action: 'STORE',
    actionLabel: '📈 भाव बढ़ेगा → स्टोर करें (STORE)',
  },
  {
    code: 'tomato',
    nameEn: 'Tomato',
    nameHi: 'टमाटर',
    nameTe: 'టమాటా',
    icon: '🍅',
    benchmarkMandi: 'Narayangaon APMC (Pune)',
    modalPrice: 1850,
    minPrice: 1400,
    maxPrice: 2100,
    trendPct: -11.2,
    action: 'SELL_NOW',
    actionLabel: '📉 गिरावट की आशंका → तुरंत बेचें (SELL)',
  },
  {
    code: 'wheat',
    nameEn: 'Wheat',
    nameHi: 'गेहूं',
    nameTe: 'గోధుమ',
    icon: '🌾',
    benchmarkMandi: 'Khanna Grain Market (Punjab)',
    modalPrice: 2420,
    minPrice: 2280,
    maxPrice: 2540,
    trendPct: 2.1,
    action: 'WATCH',
    actionLabel: '⚖️ स्थिर भाव → नियमित बिक्री (WATCH)',
  },
  {
    code: 'cotton',
    nameEn: 'Cotton',
    nameHi: 'कपास',
    nameTe: 'పత్తి',
    icon: '☁️',
    benchmarkMandi: 'Adilabad APMC (Telangana)',
    modalPrice: 7450,
    minPrice: 6900,
    maxPrice: 7800,
    trendPct: 6.4,
    action: 'STORE',
    actionLabel: '📈 तेजी का अनुमान → होल्ड करें (STORE)',
  },
  {
    code: 'potato',
    nameEn: 'Potato',
    nameHi: 'आलू',
    nameTe: 'బంగాళాదుంప',
    icon: '🥔',
    benchmarkMandi: 'Agra APMC (Uttar Pradesh)',
    modalPrice: 1680,
    minPrice: 1350,
    maxPrice: 1850,
    trendPct: 1.2,
    action: 'WATCH',
    actionLabel: '⚖️ स्थिर बाजार → मंडी तुलना करें',
  },
  {
    code: 'green_chilli',
    nameEn: 'Green Chilli',
    nameHi: 'हरी मिर्च',
    nameTe: 'పచ్చిమిర్చి',
    icon: '🌶️',
    benchmarkMandi: 'Guntur APMC Yard',
    modalPrice: 4200,
    minPrice: 3600,
    maxPrice: 4700,
    trendPct: 7.8,
    action: 'STORE',
    actionLabel: '📈 तेजी का रुख → स्टोर / ग्रेडिंग करें',
  },
]

export function LandingPage() {
  const { t } = useTranslation()
  const { activeHub } = useLocationContext()
  const [tickerPrices, setTickerPrices] = useState<MarketPriceRow[]>([])
  const [commodityFilter, setCommodityFilter] = useState<'all' | 'store' | 'sell'>('all')

  useEffect(() => {
    fetchMarketPrices()
      .then((rows) => setTickerPrices(rows.slice(0, 16)))
      .catch(() => setTickerPrices([]))
  }, [])

  const filteredCards = DEFAULT_HIGHLIGHTS.filter((item) => {
    if (commodityFilter === 'store') return item.action === 'STORE'
    if (commodityFilter === 'sell') return item.action === 'SELL_NOW'
    return true
  })

  return (
    <div className="container anim-fade-in" style={{ paddingBottom: 'var(--space-10)' }}>
      {/* 1. Header Bar */}
      <header className="stack mb-4">
        <div className="flex-between flex-wrap flex-gap-2">
          <div className="flex-center gap-3">
            <AgriPredictLogo size={40} />
            <Badge tone="success" className="badge--pulse">
              <span className="pulse-dot" /> Live Mandi Feed Active
            </Badge>
          </div>
          <div className="flex flex-gap-2">
            <button
              type="button"
              className="btn btn--secondary btn--sm"
              onClick={() => navigate('/chat')}
            >
              🎙️ AgriMitra Voice AI
            </button>
            <button
              type="button"
              className="btn btn--primary btn--sm"
              onClick={() => navigate('/signin')}
            >
              {t('auth.signIn.title')}
            </button>
          </div>
        </div>
      </header>

      {/* 2. Live Scrolling Ticker */}
      {tickerPrices.length > 0 && (
        <div className="ticker-container mb-6" aria-label="Live Mandi Spot Prices">
          <div className="ticker-track">
            {tickerPrices.concat(tickerPrices).map((p, idx) => (
              <span key={`${p.commodity_code}-${p.mandi_code}-${idx}`} className="ticker-chip">
                <span className="ticker-chip__commodity">{p.commodity_name}</span>
                <span className="ticker-chip__mandi">({p.mandi_name})</span>
                <span className="ticker-chip__price">
                  ₹{p.modal_price ? Number(p.modal_price).toLocaleString('en-IN') : 'N/A'}/{p.unit_code}
                </span>
                <span style={{ opacity: 0.4 }}>•</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 3. Hero Section with Value Proposition */}
      <section className="text-center mb-6">
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
          <Badge tone="gold">
            ⚡ AI Decision Intelligence: कब बेचें या कब स्टोर करें?
          </Badge>
        </div>
        <h1 className="text-title-xl mx-auto mb-3" style={{ maxWidth: '42rem' }}>
          Subah Ke Live Mandi Bhaav &amp; 10-Din Future Price Prediction
        </h1>
        <p className="text-body-lg mx-auto mb-5 muted" style={{ maxWidth: '38rem' }}>
          Know today&apos;s real APMC spot prices, predict 10-day price trends with custom ML,
          and know whether to <strong>STORE in warehouse</strong> or <strong>SELL immediately</strong> for highest net profit.
        </p>

        {/* Primary CTAs */}
        <div className="flex-center flex-wrap flex-gap-3" style={{ justifyContent: 'center' }}>
          <button
            type="button"
            className="btn btn--primary btn--lg"
            style={{
              boxShadow: '0 4px 18px rgba(30, 142, 98, 0.35)',
              padding: '12px 24px',
              fontWeight: 800,
            }}
            onClick={() => navigate('/analyze')}
          >
            💡 When, Where &amp; Who to Sell (स्मार्ट बिक्री सलाह)
          </button>
          <button
            type="button"
            className="btn btn--secondary btn--lg"
            onClick={() => navigate('/compare')}
          >
            ⚖️ Mandi Net Return Calculator (शुद्ध मुनाफा)
          </button>
          <button
            type="button"
            className="btn btn--secondary btn--lg"
            onClick={() => navigate('/chat')}
          >
            🎙️ Bol Kar Puchiye (Voice AI)
          </button>
        </div>
      </section>

      {/* 4. Live Agricultural Weather Advisory Component */}
      <WeatherWidget />

      {/* 5. Subah Ke Live Mandi Prices Grid (Live Commodity Rates) */}
      <section className="mb-8">
        <div className="flex-between flex-wrap flex-gap-2 mb-4">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
              <span style={{ fontSize: '20px' }}>📊</span>
              <h2 className="text-title-lg" style={{ margin: 0 }}>
                Spot Mandi Rates &amp; Action Signals ({activeHub.name})
              </h2>
            </div>
            <p className="text-body-sm muted" style={{ margin: '2px 0 0' }}>
              Agmarknet daily feed for <strong>{activeHub.district} ({activeHub.state})</strong> · Observation snapshot: <strong>Oct 17, 2026</strong>. 
              Action cues are scenario projections based on current mandi price spreads.
            </p>
          </div>

          {/* Quick Filter Tabs */}
          <div className="inline-actions">
            <button
              type="button"
              className={`filter-pill ${commodityFilter === 'all' ? 'filter-pill--active' : ''}`}
              onClick={() => setCommodityFilter('all')}
            >
              All Crops ({DEFAULT_HIGHLIGHTS.length})
            </button>
            <button
              type="button"
              className={`filter-pill ${commodityFilter === 'store' ? 'filter-pill--active' : ''}`}
              onClick={() => setCommodityFilter('store')}
            >
              📈 Store in Cold Storage ({DEFAULT_HIGHLIGHTS.filter((c) => c.action === 'STORE').length})
            </button>
            <button
              type="button"
              className={`filter-pill ${commodityFilter === 'sell' ? 'filter-pill--active' : ''}`}
              onClick={() => setCommodityFilter('sell')}
            >
              📉 Sell Today ({DEFAULT_HIGHLIGHTS.filter((c) => c.action === 'SELL_NOW').length})
            </button>
          </div>
        </div>

        {/* Commodity Cards Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: 'var(--space-4)',
          }}
        >
          {filteredCards.map((item) => (
            <div
              key={item.code}
              className="card card--interactive anim-slide-up"
              style={{
                borderRadius: 'var(--radius-xl)',
                border: item.action === 'STORE'
                  ? '2px solid var(--color-brand)'
                  : item.action === 'SELL_NOW'
                    ? '2px solid #DC2626'
                    : '1px solid var(--color-border-default)',
                background: 'var(--color-surface)',
                boxShadow: 'var(--shadow-card)',
                padding: 'var(--space-4)',
              }}
            >
              {/* Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-2)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                  <span style={{ fontSize: '28px' }}>{item.icon}</span>
                  <div>
                    <h3 style={{ margin: 0, fontSize: 'var(--font-size-md)' }}>{item.nameEn}</h3>
                    <span style={{ fontSize: '11px', color: 'var(--color-brand)', fontWeight: 600 }}>
                      {item.nameHi}
                    </span>
                  </div>
                </div>
                <Badge tone={item.action === 'STORE' ? 'success' : item.action === 'SELL_NOW' ? 'error' : 'warning'}>
                  {item.action === 'STORE' ? '📈 Rising Trend' : item.action === 'SELL_NOW' ? '📉 Falling Trend' : '⚖️ Steady'}
                </Badge>
              </div>

              {/* Price Row */}
              <div
                style={{
                  background: 'var(--color-surface-alt)',
                  padding: 'var(--space-2) var(--space-3)',
                  borderRadius: 'var(--radius-lg)',
                  margin: 'var(--space-2) 0',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span className="text-caption muted">Today&apos;s Modal Price:</span>
                  <span
                    className="num"
                    style={{ fontSize: 'var(--font-size-xl)', fontWeight: 800, color: 'var(--color-brand)' }}
                  >
                    ₹{item.modalPrice.toLocaleString('en-IN')}{' '}
                    <span style={{ fontSize: '12px', fontWeight: 400, color: 'var(--color-text-secondary)' }}>
                      / qtl
                    </span>
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginTop: '2px' }}>
                  <span className="muted">Range: ₹{item.minPrice} – ₹{item.maxPrice}</span>
                  <span className="muted">{item.benchmarkMandi} · Oct 17</span>
                </div>
              </div>

              {/* Action Banner */}
              <div
                style={{
                  background: item.action === 'STORE'
                    ? 'rgba(38, 116, 90, 0.12)'
                    : item.action === 'SELL_NOW'
                      ? 'rgba(220, 38, 38, 0.12)'
                      : 'var(--color-surface-muted)',
                  color: item.action === 'STORE'
                    ? '#153F35'
                    : item.action === 'SELL_NOW'
                      ? '#991B1B'
                      : 'var(--color-text)',
                  padding: '6px 10px',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '11px',
                  fontWeight: 700,
                  marginBottom: 'var(--space-3)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span>{item.actionLabel}</span>
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                <Button
                  variant="primary"
                  className="btn--sm"
                  style={{ flex: 1.2, fontWeight: 700 }}
                  onClick={() => navigate('/analyze')}
                >
                  💡 Complete Advice →
                </Button>
                <Button
                  variant="secondary"
                  className="btn--sm"
                  style={{ flex: 1 }}
                  onClick={() => navigate('/compare')}
                >
                  Mandi Net Return
                </Button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 6. The 3-Step Decision Support Flow */}
      <section
        className="section mb-8"
        style={{
          background: 'var(--color-surface-alt)',
          border: '1px solid var(--color-border-default)',
          borderRadius: 'var(--radius-2xl)',
          padding: 'var(--space-6) var(--space-5)',
        }}
      >
        <div className="text-center mb-6">
          <span className="eyebrow">HOW AGRIPREDICT AI WORKS (काम कैसे करता है)</span>
          <h2 className="text-title-lg mx-auto mb-1">
            3 Simple Steps to True Maximum Profit
          </h2>
          <p className="text-body-md muted mx-auto" style={{ maxWidth: '30rem' }}>
            Never sell on headline prices alone. Follow the real decision formula:
          </p>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: 'var(--space-4)',
          }}
        >
          <div className="card" style={{ background: '#FFFFFF' }}>
            <span style={{ fontSize: '28px' }}>1️⃣</span>
            <h3 style={{ margin: 'var(--space-2) 0 var(--space-1)' }}>
              Check Morning Prices (मंडी भाव)
            </h3>
            <p className="text-body-sm muted">
              Verified daily Agmarknet arrivals across 1,830 mandis. Search by crop, district, and APMC yard before loading your truck.
            </p>
          </div>

          <div className="card" style={{ background: '#FFFFFF', border: '2px solid var(--color-brand)' }}>
            <span style={{ fontSize: '28px' }}>2️⃣</span>
            <h3 style={{ margin: 'var(--space-2) 0 var(--space-1)' }}>
              10-Day Horizon Projection (स्टोर या बेचें?)
            </h3>
            <p className="text-body-sm muted">
              Scenario price projection model based on seasonal volatility. Compare expected storage gains against cold storage tariffs before deciding to store or sell.
            </p>
          </div>

          <div className="card" style={{ background: '#FFFFFF' }}>
            <span style={{ fontSize: '28px' }}>3️⃣</span>
            <h3 style={{ margin: 'var(--space-2) 0 var(--space-1)' }}>
              Compare Mandis (शुद्ध कमाई)
            </h3>
            <p className="text-body-sm muted">
              Deduct diesel transport, APMC market cess, and loading charges to see which market yields the highest in-hand cash.
            </p>
          </div>
        </div>
      </section>

      {/* 7. Dedicated 4-User Role Workspaces */}
      <section className="mb-8">
        <div className="text-center mb-5">
          <span className="eyebrow">ROLE-BASED WORKSPACES (सभी उपयोगकर्ताओं के डैशबोर्ड)</span>
          <h2 className="text-title-lg mx-auto">
            Built for Every Agricultural Participant
          </h2>
          <p className="text-body-md muted mx-auto">
            Choose your role to open your dedicated workspace and operations:
          </p>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
            gap: 'var(--space-4)',
          }}
        >
          {/* Role 1: Farmer */}
          <div
            className="card card--interactive"
            onClick={() => navigate('/dashboard/farmer')}
            style={{ borderRadius: 'var(--radius-xl)', padding: 'var(--space-5)' }}
          >
            <div style={{ fontSize: '36px', marginBottom: 'var(--space-2)' }}>👨‍🌾</div>
            <h3 style={{ margin: 0 }}>Farmer (किसान / రైతు)</h3>
            <p className="text-body-sm muted" style={{ margin: 'var(--space-2) 0 var(--space-4)' }}>
              Live market intelligence, Store vs Sell decision, net return comparison, matched schemes, and voluntary produce selling.
            </p>
            <Button variant="primary" className="btn--sm">
              Open Farmer Dashboard →
            </Button>
          </div>

          {/* Role 2: Transporter */}
          <div
            className="card card--interactive"
            onClick={() => navigate('/dashboard/transport')}
            style={{ borderRadius: 'var(--radius-xl)', padding: 'var(--space-5)' }}
          >
            <div style={{ fontSize: '36px', marginBottom: 'var(--space-2)' }}>🚛</div>
            <h3 style={{ margin: 0 }}>Transporter (ट्रांसपोर्टर)</h3>
            <p className="text-body-sm muted" style={{ margin: 'var(--space-2) 0 var(--space-4)' }}>
              Manage commercial vehicle fleet, view farmer freight booking inquiries, calculate diesel margins, and submit trip quotes.
            </p>
            <Button variant="secondary" className="btn--sm">
              Open Transport Dashboard →
            </Button>
          </div>

          {/* Role 3: Warehouse Owner */}
          <div
            className="card card--interactive"
            onClick={() => navigate('/dashboard/storage')}
            style={{ borderRadius: 'var(--radius-xl)', padding: 'var(--space-5)' }}
          >
            <div style={{ fontSize: '36px', marginBottom: 'var(--space-2)' }}>🏭</div>
            <h3 style={{ margin: 0 }}>Warehouse &amp; Cold Storage (गोदाम)</h3>
            <p className="text-body-sm muted" style={{ margin: 'var(--space-2) 0 var(--space-4)' }}>
              Capacity utilization gauge, publish rental charges, accept inward farmer storage bookings, and notify farmers at peak prices.
            </p>
            <Button variant="secondary" className="btn--sm">
              Open Storage Dashboard →
            </Button>
          </div>

          {/* Role 4: Buyer */}
          <div
            className="card card--interactive"
            onClick={() => navigate('/dashboard/buyer')}
            style={{ borderRadius: 'var(--radius-xl)', padding: 'var(--space-5)' }}
          >
            <div style={{ fontSize: '36px', marginBottom: 'var(--space-2)' }}>🤝</div>
            <h3 style={{ margin: 0 }}>Buyer &amp; Trader (खरीदार / వ్యాపారి)</h3>
            <p className="text-body-sm muted" style={{ margin: 'var(--space-2) 0 var(--space-4)' }}>
              Post bulk procurement requirements, browse available farmer produce lots, and negotiate transparent institutional contracts.
            </p>
            <Button variant="secondary" className="btn--sm">
              Open Buyer Dashboard →
            </Button>
          </div>
        </div>
      </section>

      {/* 8. Voice AI Banner */}
      <div
        className="card anim-slide-up mb-8"
        style={{
          background: 'linear-gradient(135deg, #153F35 0%, #26745A 100%)',
          color: '#FFFFFF',
          borderRadius: 'var(--radius-2xl)',
          padding: 'var(--space-6) var(--space-6)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 'var(--space-4)',
        }}
      >
        <div style={{ maxWidth: '32rem' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
            <span style={{ fontSize: '24px' }}>🎙️</span>
            <Badge tone="gold">Bhashini &amp; Multilingual Voice AI</Badge>
          </div>
          <h2 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 800, margin: '0 0 var(--space-2)', color: '#FFFFFF' }}>
            AgriMitra AI: Bol Kar Puchiye (बोलकर पूछिए)
          </h2>
          <p style={{ margin: 0, fontSize: 'var(--font-size-sm)', opacity: 0.9 }}>
            Don&apos;t want to type? Speak in <strong>Hindi, Telugu, or English</strong>.
            Ask about crop prices, whether to store or sell, truck freight rates, and government scheme eligibility.
          </p>
        </div>

        <Button
          variant="gold"
          style={{ padding: '12px 24px', fontSize: 'var(--font-size-md)', fontWeight: 700 }}
          onClick={() => navigate('/chat')}
        >
          🎙️ Talk to AgriMitra AI Now →
        </Button>
      </div>

      {/* 9. Live Health Status */}
      <footer className="text-center">
        <HealthStatus />
      </footer>
    </div>
  )
}
