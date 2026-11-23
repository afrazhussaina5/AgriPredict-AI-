import { useMemo, useState } from 'react'
import { Badge, Button, Card } from '../components/ui'
import { useTranslation } from '../i18n/useTranslation'
import { navigate } from '../router'
import { useLocationContext } from '../context/LocationContext'

type Scheme = {
  id: string
  name: string
  category: 'income' | 'insurance' | 'equipment' | 'infra'
  authority: string
  benefitText: string
  officialUrl: string
  lastVerifiedDate: string
  criteriaList: { label: string; matched: boolean; note?: string }[]
  minLandHa?: number
  maxLandHa?: number
  requiresOwnership?: boolean
}

const SCHEMES_DATA: Scheme[] = [
  {
    id: 'pm-kisan',
    name: 'PM-Kisan Samman Nidhi',
    category: 'income',
    authority: 'Ministry of Agriculture & Farmers Welfare, GoI',
    benefitText: '₹6,000 per year (3 equal installments of ₹2,000 via DBT)',
    officialUrl: 'https://pmkisan.gov.in',
    lastVerifiedDate: '2026-09-15',
    requiresOwnership: true,
    criteriaList: [
      { label: 'Cultivable landholding in farmer family name', matched: true },
      { label: 'Aadhaar-seeded active bank account', matched: true },
      { label: 'Non-institutional landholder (individual/family)', matched: true },
      {
        label: 'Exclusion check (Income tax payer / constitutional post holder)',
        matched: true,
        note: 'Self-declaration',
      },
    ],
  },
  {
    id: 'pmfby',
    name: 'Pradhan Mantri Fasal Bima Yojana (PMFBY)',
    category: 'insurance',
    authority: 'Department of Agriculture & Cooperation, GoI',
    benefitText: 'Comprehensive risk insurance with only 1.5% - 2.0% farmer premium',
    officialUrl: 'https://pmfby.gov.in',
    lastVerifiedDate: '2026-08-30',
    requiresOwnership: false,
    criteriaList: [
      { label: 'Growing notified crop in notified insurance unit/village', matched: true },
      {
        label: 'Both loanee and non-loanee sharecroppers / tenant farmers eligible',
        matched: true,
      },
      { label: 'Sowing certificate / land possession record verified', matched: true },
      {
        label: 'Enrolled within seasonal cutoff deadline',
        matched: true,
        note: 'Check state portal for Kharif/Rabi cutoffs',
      },
    ],
  },
  {
    id: 'aif',
    name: 'Agriculture Infrastructure Fund (AIF)',
    category: 'infra',
    authority: 'National Bank for Agriculture and Rural Development (NABARD) / MoA&FW',
    benefitText: '3% p.a. interest subvention on loans up to ₹2 Crore + CGTMSE credit guarantee',
    officialUrl: 'https://agriinfra.dac.gov.in',
    lastVerifiedDate: '2026-09-01',
    requiresOwnership: false,
    criteriaList: [
      {
        label: 'Post-harvest infrastructure project (Packhouse, Cold Room, Sorting Unit)',
        matched: true,
      },
      { label: 'Eligible entity: Individual farmer, FPO, PACS, Agri-entrepreneur', matched: true },
      {
        label: 'Viable Detailed Project Report (DPR)',
        matched: false,
        note: 'Required during bank appraisal',
      },
    ],
  },
  {
    id: 'smam',
    name: 'Sub-Mission on Agricultural Mechanization (SMAM)',
    category: 'equipment',
    authority: 'Directorate of Agricultural Mechanization / State Departments',
    benefitText: '40% to 50% capital subsidy on tractors, power tillers, rotavators, and laser levellers',
    officialUrl: 'https://agrimachinery.nic.in',
    lastVerifiedDate: '2026-07-20',
    requiresOwnership: true,
    criteriaList: [
      {
        label: 'Small and marginal farmers receive higher 50% subsidy priority',
        matched: true,
      },
      { label: 'Valid land revenue record (7/12, RoR, Patta)', matched: true },
      {
        label: 'Must not have availed subsidy on same implement within 5 years',
        matched: true,
      },
      {
        label: 'Purchase from empanelled manufacturer / authorized dealer',
        matched: true,
        note: 'DBT-linked subsidy',
      },
    ],
  },
  {
    id: 'kcc',
    name: 'Kisan Credit Card (KCC) Concessional Loan',
    category: 'income',
    authority: 'Reserve Bank of India & NABARD',
    benefitText: 'Short-term crop production loan up to ₹3,00,000 at effective 4% interest p.a.',
    officialUrl: 'https://www.myscheme.gov.in/schemes/kcc',
    lastVerifiedDate: '2026-09-10',
    requiresOwnership: false,
    criteriaList: [
      {
        label: 'Owner cultivator, tenant farmer, oral lessee or sharecropper',
        matched: true,
      },
      {
        label: 'Prompt repayment subvention (3% discount for on-time payment)',
        matched: true,
      },
      { label: 'Clean credit history without willful default', matched: true },
    ],
  },
]

const CATEGORY_ICON: Record<string, string> = {
  income: '💰',
  insurance: '🛡️',
  equipment: '🚜',
  infra: '🏗️',
}

export function GovernmentSchemesPage() {
  const { t } = useTranslation()
  const { activeHub } = useLocationContext()
  const [activeFilter, setActiveFilter] = useState<
    'all' | 'income' | 'insurance' | 'equipment' | 'infra'
  >('all')
  const [landCategory, setLandCategory] = useState<'small' | 'large'>('small')
  const [isOwner, setIsOwner] = useState<boolean>(true)

  const filteredSchemes = useMemo(() => {
    return SCHEMES_DATA.filter((s) => {
      if (activeFilter !== 'all' && s.category !== activeFilter) return false
      return true
    })
  }, [activeFilter])

  return (
    <div className="wrapper section anim-fade-in">
      <div className="stack">
        <div>
          <p className="eyebrow mb-1">{t('nav.schemes')}</p>
          <h1>{t('schemes.title')}</h1>
          <p className="lede">{t('schemes.subtitle')}</p>
        </div>

        {/* Official verification disclaimer */}
        <div className="alert alert--info">
          <div className="alert__body">
            <p className="alert__title">🏛️ Official Verification Guarantee &amp; State Context ({activeHub.state})</p>
            <p className="text-sm muted">
              All welfare schemes are verified against official GoI and {activeHub.state} Department of Agriculture portals. Direct Benefit Transfer (DBT) funds are credited strictly to Aadhaar-seeded bank accounts without platform commission.
            </p>
          </div>
        </div>

        {/* Farmer Profile Criteria Filter */}
        <Card title="Quick Eligibility Matcher" accent>
          <div
            className="card-grid"
            style={{ alignItems: 'center' }}
          >
            <div className="field">
              <label htmlFor="scheme-land-category" className="field__label">
                Landholding Category
              </label>
              <select
                id="scheme-land-category"
                className="field__select"
                value={landCategory}
                onChange={(e) => setLandCategory(e.target.value as 'small' | 'large')}
              >
                <option value="small">
                  Small / Marginal Farmer (Up to 2 Hectares / 5 Acres)
                </option>
                <option value="large">Medium / Large Farmer (More than 2 Hectares)</option>
              </select>
            </div>

            <div className="field">
              <label htmlFor="scheme-land-ownership" className="field__label">
                Land Ownership Status
              </label>
              <select
                id="scheme-land-ownership"
                className="field__select"
                value={isOwner ? 'owner' : 'tenant'}
                onChange={(e) => setIsOwner(e.target.value === 'owner')}
              >
                <option value="owner">Title Owner / Family Landholder (ज़मीन मालिक)</option>
                <option value="tenant">Tenant Farmer / Sharecropper (किरायेदार / बटाईदार)</option>
              </select>
            </div>
          </div>
        </Card>

        {/* Category Filter Tabs */}
        <div
          className="inline-actions"
          style={{ overflowX: 'auto', paddingBottom: 'var(--space-1)', flexWrap: 'wrap' }}
        >
          <Button
            variant={activeFilter === 'all' ? 'primary' : 'secondary'}
            onClick={() => setActiveFilter('all')}
          >
            {t('schemes.filterAll')} ({SCHEMES_DATA.length})
          </Button>
          <Button
            variant={activeFilter === 'income' ? 'primary' : 'secondary'}
            onClick={() => setActiveFilter('income')}
          >
            💰 {t('schemes.filterIncome')}
          </Button>
          <Button
            variant={activeFilter === 'insurance' ? 'primary' : 'secondary'}
            onClick={() => setActiveFilter('insurance')}
          >
            🛡️ {t('schemes.filterInsurance')}
          </Button>
          <Button
            variant={activeFilter === 'equipment' ? 'primary' : 'secondary'}
            onClick={() => setActiveFilter('equipment')}
          >
            🚜 {t('schemes.filterEquipment')}
          </Button>
          <Button
            variant={activeFilter === 'infra' ? 'primary' : 'secondary'}
            onClick={() => setActiveFilter('infra')}
          >
            🏗️ {t('schemes.filterInfra')}
          </Button>
        </div>

        {/* Scheme Cards Grid */}
        <div className="stack">
          {filteredSchemes.map((scheme) => {
            const hasOwnershipIssue = scheme.requiresOwnership && !isOwner
            const matchStatus = hasOwnershipIssue ? 'more_info' : 'match'

            return (
              <div key={scheme.id} className="card anim-slide-up">
                <div className="card__header">
                  <div>
                    <h3 style={{ margin: 0 }}>
                      {CATEGORY_ICON[scheme.category]} {scheme.name}
                    </h3>
                    <p className="text-caption muted" style={{ margin: 'var(--space-1) 0 0' }}>
                      {scheme.authority} · Verified on {scheme.lastVerifiedDate}
                    </p>
                  </div>
                  <div>
                    {matchStatus === 'match' ? (
                      <Badge tone="success">✓ {t('schemes.match')}</Badge>
                    ) : (
                      <Badge tone="warning">⚠️ Land record needed</Badge>
                    )}
                  </div>
                </div>

                {/* Benefit Highlight */}
                <div
                  style={{
                    background: 'var(--color-surface-alt)',
                    padding: 'var(--space-3)',
                    borderRadius: 'var(--radius-md)',
                    margin: 'var(--space-2) 0 var(--space-3)',
                  }}
                >
                  <p className="text-xs eyebrow" style={{ margin: 0 }}>
                    {t('schemes.benefit')}
                  </p>
                  <p
                    className="text-strong num"
                    style={{ margin: 'var(--space-1) 0 0', fontSize: 'var(--font-size-md)' }}
                  >
                    🎯 {scheme.benefitText}
                  </p>
                </div>

                {/* Criteria Checklist */}
                <div>
                  <p className="text-sm text-strong" style={{ marginBottom: 'var(--space-2)' }}>
                    {t('schemes.criteria')}:
                  </p>
                  <ul className="plain-list text-sm">
                    {scheme.criteriaList.map((crit, idx) => (
                      <li
                        key={idx}
                        style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: 'var(--space-2)',
                          margin: 'var(--space-1) 0',
                        }}
                      >
                        <span
                          style={{
                            color: crit.matched ? 'var(--color-success)' : 'var(--color-warning)',
                            flexShrink: 0,
                          }}
                        >
                          {crit.matched ? '✅' : '⚠️'}
                        </span>
                        <span>
                          {crit.label}
                          {crit.note && (
                            <span className="muted"> ({crit.note})</span>
                          )}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Footer Action */}
                <div
                  className="card__footer"
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                >
                  <span className="text-caption muted">Official Government Application</span>
                  <a
                    href={scheme.officialUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn--primary btn--sm"
                  >
                    {t('schemes.officialPortal')} ↗
                  </a>
                </div>
              </div>
            )
          })}
        </div>

        {/* Navigation Actions */}
        <div className="inline-actions" style={{ justifyContent: 'space-between' }}>
          <Button variant="secondary" onClick={() => navigate('/dashboard')}>
            ← Back to Dashboard
          </Button>
          <Button variant="primary" onClick={() => navigate('/market')}>
            Check Market Prices →
          </Button>
        </div>
      </div>
    </div>
  )
}
