import { useId, useMemo, useState } from 'react'
import { useAuth } from '../auth/context'
import { Badge, Button, Card } from '../components/ui'
import { useToast } from '../components/Toast'
import { useTranslation } from '../i18n/useTranslation'
import { navigate } from '../router'
import { useLocationContext } from '../context/LocationContext'

type BuyerRequirement = {
  id: string
  buyerName: string
  category: 'Corporate' | 'FPO' | 'APMC Trader' | 'Processor'
  verified: boolean
  commodity: string
  variety?: string
  minQuantityQtl: number
  targetPricePerQtl: number
  location: string
  paymentTerms: string
  deliveryTerms: string
  expiryDate: string
}

const INITIAL_BUYERS: BuyerRequirement[] = [
  {
    id: 'b1',
    buyerName: 'Reliance Retail (Fresh Produce Division)',
    category: 'Corporate',
    verified: true,
    commodity: 'Onion',
    variety: 'Nashik Red / Garwa',
    minQuantityQtl: 30,
    targetPricePerQtl: 2520,
    location: 'Nashik Collection Hub, Maharashtra',
    paymentTerms: 'T+2 Days Direct NEFT / RTGS Bank Transfer',
    deliveryTerms: 'Farmgate Pickup (Buyer arranges transport)',
    expiryDate: '2026-10-25',
  },
  {
    id: 'b2',
    buyerName: 'ITC Agri Business (Direct Procurement)',
    category: 'Corporate',
    verified: true,
    commodity: 'Wheat',
    variety: 'Sharbati / Lokwan',
    minQuantityQtl: 50,
    targetPricePerQtl: 2460,
    location: 'Indore Processing Unit, Madhya Pradesh',
    paymentTerms: 'Immediate Payment on Weighment & Quality Slip',
    deliveryTerms: 'Delivery to Nearest e-Choupal / Mandi Hub',
    expiryDate: '2026-10-30',
  },
  {
    id: 'b3',
    buyerName: 'BigBasket (Innovative Retail Sourcing)',
    category: 'Corporate',
    verified: true,
    commodity: 'Tomato',
    variety: 'Hybrid Standard A-Grade',
    minQuantityQtl: 20,
    targetPricePerQtl: 2180,
    location: 'Pune Regional Fulfillment Center',
    paymentTerms: 'Weekly Settlement via Direct Bank Credit',
    deliveryTerms: 'Crates provided by buyer at farmgate',
    expiryDate: '2026-10-18',
  },
  {
    id: 'b4',
    buyerName: 'Sahyadri Farmers Producer Co. Ltd.',
    category: 'FPO',
    verified: true,
    commodity: 'Onion',
    variety: 'Pusa Red / Bhima Super',
    minQuantityQtl: 25,
    targetPricePerQtl: 2480,
    location: 'Mohadi Post-Harvest Complex, Nashik',
    paymentTerms: 'T+1 Day Member / Farmer Direct Bank Transfer',
    deliveryTerms: 'Assisted Freight Subsidy Available',
    expiryDate: '2026-10-22',
  },
  {
    id: 'b5',
    buyerName: 'Adilabad Cotton Ginning & Pressing Mills',
    category: 'Processor',
    verified: true,
    commodity: 'Cotton',
    variety: 'Medium / Long Staple',
    minQuantityQtl: 40,
    targetPricePerQtl: 7450,
    location: 'Adilabad Industrial Area, Telangana',
    paymentTerms: 'Same-day Bank RTGS after Moisture Test',
    deliveryTerms: 'Delivery at Mill Gate',
    expiryDate: '2026-11-05',
  },
]

export function BuyerMarketplacePage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const { activeHub } = useLocationContext()
  const { showToast } = useToast()
  const [selectedCrop, setSelectedCrop] = useState<string>('all')
  const [onlyLocalHub, setOnlyLocalHub] = useState<boolean>(false)
  const [inquiredIds, setInquiredIds] = useState<Set<string>>(new Set())
  const [showPostModal, setShowPostModal] = useState<boolean>(false)

  // Buyer Form State
  const [reqCommodity, setReqCommodity] = useState('Onion')
  const [reqQty, setReqQty] = useState('50')
  const [reqPrice, setReqPrice] = useState('2500')
  const [reqLocation, setReqLocation] = useState('')
  const [postSuccess, setPostSuccess] = useState(false)

  const isBuyer = user?.roles.includes('buyer')

  const filterId = useId()
  const reqCropId = useId()
  const reqQtyId = useId()
  const reqPriceId = useId()
  const reqLocId = useId()

  const buyersList = useMemo(() => {
    let list = INITIAL_BUYERS
    if (selectedCrop !== 'all') {
      list = list.filter((b) => b.commodity.toLowerCase() === selectedCrop.toLowerCase())
    }
    if (onlyLocalHub) {
      list = list.filter(
        (b) =>
          b.location.toLowerCase().includes(activeHub.state.toLowerCase()) ||
          b.location.toLowerCase().includes(activeHub.district.toLowerCase()) ||
          b.commodity.toLowerCase() === activeHub.dominantCrop.toLowerCase()
      )
    }
    return list
  }, [selectedCrop, onlyLocalHub, activeHub])

  function handlePostRequirement(e: React.FormEvent) {
    e.preventDefault()
    setPostSuccess(true)
    setTimeout(() => {
      setPostSuccess(false)
      setShowPostModal(false)
    }, 1500)
  }

  return (
    <div className="wrapper section anim-fade-in">
      <div className="stack">

        {/* Page Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
          <div>
            <p className="eyebrow mb-1">{t('nav.buyers')}</p>
            <h1>{t('buyers.title')}</h1>
            <p className="lede">{t('buyers.subtitle')}</p>
          </div>
          {isBuyer && (
            <Button variant="primary" onClick={() => setShowPostModal(true)}>
              + {t('buyers.postReq')}
            </Button>
          )}
        </div>

        {/* Sample data disclaimer */}
        <div style={{
          background: 'var(--color-warm-soft)',
          border: '1px solid var(--color-warm-bg)',
          borderRadius: 'var(--radius-md)',
          padding: 'var(--space-3) var(--space-4)',
          display: 'flex',
          gap: 'var(--space-2)',
          alignItems: 'flex-start',
          fontSize: 'var(--font-size-xs)',
          color: 'var(--color-warm-ink)',
        }}>
          <span style={{ fontSize: 16, lineHeight: 1 }}>⚠️</span>
          <span>
            <strong>Sample listings for demonstration.</strong>{' '}
            In production, buyer requirements will be verified corporate entities registered with APMC / FSSAI.
            Prices shown are the buyer's stated offer — always compare with current mandi prices before agreeing.
            Use the{' '}
            <button
              type="button"
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-brand)', textDecoration: 'underline', padding: 0, fontSize: 'inherit' }}
              onClick={() => navigate('/compare')}
            >
              Mandi Comparison tool
            </button>
            {' '}to verify your net realization.
          </span>
        </div>

        {/* Filter Bar */}
        <Card>
          <div className="card-grid" style={{ alignItems: 'center' }}>
            <div className="field">
              <label htmlFor={filterId} className="field__label">Filter by Commodity</label>
              <select
                id={filterId}
                className="select"
                value={selectedCrop}
                onChange={(e) => setSelectedCrop(e.target.value)}
              >
                <option value="all">All Commodities (All Verified Demands)</option>
                <option value="onion">Onion (कांदा / ఉల్లిపాయ)</option>
                <option value="tomato">Tomato (टमाटर / టమాటా)</option>
                <option value="cotton">Cotton (कपास / పత్తి)</option>
                <option value="wheat">Wheat (गेहूं / గోధుమ)</option>
              </select>
            </div>
            <div>
              <p className="field__label">Local Hub Regional Filter</p>
              <button
                type="button"
                className={`btn btn--sm ${onlyLocalHub ? 'btn--primary' : 'btn--secondary'}`}
                style={{ marginTop: 'var(--space-1)' }}
                onClick={() => setOnlyLocalHub((prev) => !prev)}
              >
                {onlyLocalHub ? `✓ Showing ${activeHub.district} & ${activeHub.state} Only` : `📍 Filter for ${activeHub.district} / ${activeHub.dominantCrop}`}
              </button>
            </div>
          </div>
        </Card>

        {/* Buyer Requirement Listings */}
        <div className="stack">
          {buyersList.map((buyer) => (
            <div key={buyer.id} className="card anim-slide-up">
              <div className="card__header">
                <div>
                  <h3 style={{ margin: 0 }}>{buyer.buyerName}</h3>
                  <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-1)', alignItems: 'center' }}>
                    <Badge tone="success">🛡️ {buyer.category}</Badge>
                    <span className="text-caption muted">📍 {buyer.location}</span>
                  </div>
                </div>

                <div className="metric-group" style={{ textAlign: 'end' }}>
                  <span className="metric-group__val text-strong" style={{ color: 'var(--color-primary-strong)' }}>
                    ₹{buyer.targetPricePerQtl.toLocaleString('en-IN')}
                  </span>
                  <span className="metric-group__unit">per quintal</span>
                </div>
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                  gap: 'var(--space-3)',
                  padding: 'var(--space-3)',
                  background: 'var(--color-surface-alt)',
                  borderRadius: 'var(--radius-md)',
                  margin: 'var(--space-3) 0',
                }}
              >
                <div>
                  <span className="eyebrow">Commodity & Variety</span>
                  <p className="text-strong" style={{ margin: 'var(--space-1) 0 0' }}>
                    {buyer.commodity} {buyer.variety ? `(${buyer.variety})` : ''}
                  </p>
                </div>
                <div>
                  <span className="eyebrow">{t('buyers.minQuantity')}</span>
                  <p className="text-strong num" style={{ margin: 'var(--space-1) 0 0' }}>
                    {buyer.minQuantityQtl} Quintals (≈ {Math.round(buyer.minQuantityQtl * 0.1)} Tonnes)
                  </p>
                </div>
                <div>
                  <span className="eyebrow">{t('buyers.paymentTerms')}</span>
                  <p className="text-sm" style={{ margin: 'var(--space-1) 0 0' }}>
                    {buyer.paymentTerms}
                  </p>
                </div>
                <div>
                  <span className="eyebrow">{t('buyers.deliveryTerms')}</span>
                  <p className="text-sm" style={{ margin: 'var(--space-1) 0 0' }}>
                    {buyer.deliveryTerms}
                  </p>
                </div>
              </div>

              <div className="card__footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="text-caption muted">
                  Requirement active until {buyer.expiryDate}
                </span>

                {inquiredIds.has(buyer.id) ? (
                  <Badge tone="success">✓ Inquiry Sent! Contact shared via SMS.</Badge>
                ) : (
                  <Button
                    variant="primary"
                    className="btn--sm"
                    onClick={() => {
                      setInquiredIds((prev) => new Set([...prev, buyer.id]))
                      showToast(
                        `Inquiry sent to ${buyer.buyerName}. Their contact details have been sent to your registered mobile.`,
                        'success'
                      )
                    }}
                  >
                    🤝 Express Interest / Connect
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Post Requirement Modal for Buyers */}
        {showPostModal && (
          <div className="card anim-scale-in" style={{ border: '2px solid var(--color-primary)' }}>
            <div className="card__header">
              <h3>Post Commercial Procurement Requirement</h3>
              <Button variant="ghost" onClick={() => setShowPostModal(false)}>✕</Button>
            </div>
            {postSuccess ? (
              <div className="alert alert--success">
                <p className="alert__title">Requirement Published Successfully!</p>
                <p>Farmers matching your commodity criteria will now be notified.</p>
              </div>
            ) : (
              <form onSubmit={handlePostRequirement} className="stack">
                <div className="card-grid">
                  <div className="field">
                    <label htmlFor={reqCropId} className="field__label">Commodity</label>
                    <input
                      id={reqCropId}
                      className="input"
                      value={reqCommodity}
                      onChange={(e) => setReqCommodity(e.target.value)}
                      required
                    />
                  </div>
                  <div className="field">
                    <label htmlFor={reqQtyId} className="field__label">Quantity (Quintals)</label>
                    <input
                      id={reqQtyId}
                      type="number"
                      className="input"
                      value={reqQty}
                      onChange={(e) => setReqQty(e.target.value)}
                      required
                    />
                  </div>
                  <div className="field">
                    <label htmlFor={reqPriceId} className="field__label">Offered Price (₹ / Quintal)</label>
                    <input
                      id={reqPriceId}
                      type="number"
                      className="input"
                      value={reqPrice}
                      onChange={(e) => setReqPrice(e.target.value)}
                      required
                    />
                  </div>
                  <div className="field">
                    <label htmlFor={reqLocId} className="field__label">Collection Point / Mandi Area</label>
                    <input
                      id={reqLocId}
                      className="input"
                      placeholder="e.g. Lasalgaon / Pune Central"
                      value={reqLocation}
                      onChange={(e) => setReqLocation(e.target.value)}
                      required
                    />
                  </div>
                </div>
                <div className="inline-actions">
                  <Button type="submit" variant="primary">Publish Requirement</Button>
                  <Button variant="secondary" onClick={() => setShowPostModal(false)}>Cancel</Button>
                </div>
              </form>
            )}
          </div>
        )}

        {/* Footer Navigation */}
        <div className="inline-actions" style={{ justifyContent: 'space-between' }}>
          <Button variant="secondary" onClick={() => navigate('/compare')}>
            ← Check Mandi Differences First
          </Button>
          <Button variant="primary" onClick={() => navigate('/services')}>
            Find Transport & Storage →
          </Button>
        </div>
      </div>
    </div>
  )
}
