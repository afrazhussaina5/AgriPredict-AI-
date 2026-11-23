import { useState, type FormEvent } from 'react'

import { ApiError, requestOtp, type UserRole } from '../api/client'
import { useAuth } from '../auth/context'
import { TextField } from '../components/fields'
import { Alert, Badge, Button } from '../components/ui'
import { LoadingState } from '../components/states'
import type { TranslationKey } from '../i18n/translations'
import { useTranslation } from '../i18n/useTranslation'
import { navigate } from '../router'

type RoleOption = {
  role: UserRole
  labelKey: TranslationKey
  hintKey: TranslationKey
}

const ROLE_OPTIONS: RoleOption[] = [
  { role: 'farmer', labelKey: 'auth.role.farmer', hintKey: 'auth.role.farmer.hint' },
  { role: 'buyer', labelKey: 'auth.role.buyer', hintKey: 'auth.role.buyer.hint' },
  {
    role: 'transport_provider',
    labelKey: 'auth.role.transport',
    hintKey: 'auth.role.transport.hint',
  },
  {
    role: 'storage_provider',
    labelKey: 'auth.role.storage',
    hintKey: 'auth.role.storage.hint',
  },
]

type DemoAccount = {
  role: UserRole
  name: string
  location: string
  phone: string
  icon: string
  badge: string
  description: string
  dest: string
}

const DEMO_ACCOUNTS: DemoAccount[] = [
  {
    role: 'farmer',
    name: 'Ramesh Patil',
    location: 'Lasalgaon, Nashik (Maharashtra)',
    phone: '+919876500001',
    icon: '👨‍🌾',
    badge: 'Farmer (किसान / రైతు)',
    description: 'Check morning mandi rates, 10-day price forecast, voluntary produce selling & net returns.',
    dest: '/dashboard/farmer',
  },
  {
    role: 'transport_provider',
    name: 'Sunil Freight Logistics',
    location: 'Pimpalgaon Hub (Maharashtra)',
    phone: '+919876500002',
    icon: '🚛',
    badge: 'Transporter (ट्रांसपोर्टर)',
    description: 'Manage mini-truck fleet, accept farmer load requests & calculate diesel trip margins.',
    dest: '/dashboard/transport',
  },
  {
    role: 'storage_provider',
    name: 'Sahyadri Agro Warehousing',
    location: 'Niphad Godown Hub (Nashik)',
    phone: '+919876500003',
    icon: '🏭',
    badge: 'Storage & Cold Chain (गोदाम)',
    description: 'Chamber telematics (temp/humidity), WDRA e-NWR receipts, tariff management & alerts.',
    dest: '/dashboard/storage',
  },
  {
    role: 'buyer',
    name: 'Kisan Mart Procurement',
    location: 'Vashi Wholesale Terminal (Mumbai)',
    phone: '+919876500004',
    icon: '🤝',
    badge: 'Wholesale Buyer (व्यापारी)',
    description: 'Post bulk procurement demands, review farmgate produce lots & transparent contracts.',
    dest: '/dashboard/buyer',
  },
]

export function AuthPage() {
  const { t, locale } = useTranslation()
  const auth = useAuth()

  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'instant' | 'phone'>('instant')

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : t('state.error.body'))
    } finally {
      setBusy(false)
    }
  }

  function handleDemoLogin(account: DemoAccount) {
    void run(async () => {
      await auth.loginAsDemoRole(account.role, account.name, account.phone)
      navigate(account.dest)
    })
  }

  function submitPhone(event: FormEvent) {
    event.preventDefault()
    void run(async () => {
      const result = await requestOtp(phone)
      auth.begin(phone, result.dev_code, result.phone_masked)
    })
  }

  function submitCode(event: FormEvent) {
    event.preventDefault()
    void run(async () => {
      await auth.completeVerification(code)
    })
  }

  function submitOnboarding(event: FormEvent) {
    event.preventDefault()
    void run(async () => {
      await auth.finishOnboarding(displayName, locale)
      navigate('/dashboard')
    })
  }

  return (
    <div className="container anim-fade-in" style={{ maxWidth: 860, paddingBottom: 'var(--space-10)' }}>
      {/* Header */}
      <div className="page-header text-center" style={{ marginBottom: 'var(--space-6)' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
          <img
            src="/logo.png"
            alt="AgriPredict Logo"
            width={48}
            height={48}
            style={{ borderRadius: '10px', boxShadow: '0 2px 8px rgba(0,0,0,0.15)' }}
          />
          <Badge tone="gold">AgriPredict AI Authentication</Badge>
        </div>
        <h1 className="text-title-xl mx-auto" style={{ margin: '0 0 var(--space-2)' }}>
          Choose Your Agricultural Role Login
        </h1>
        <p className="text-body-md muted mx-auto" style={{ maxWidth: '38rem' }}>
          Separate workspaces tailored for Farmers, Logistics Transporters, Cold Storage Operators, and Institutional Buyers.
        </p>

        {/* Tab switch */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: 'var(--space-2)', marginTop: 'var(--space-4)' }}>
          <button
            type="button"
            className={`filter-pill ${activeTab === 'instant' ? 'filter-pill--active' : ''}`}
            onClick={() => setActiveTab('instant')}
          >
            ⚡ 1-Click Instant Role Login (Recommended)
          </button>
          <button
            type="button"
            className={`filter-pill ${activeTab === 'phone' ? 'filter-pill--active' : ''}`}
            onClick={() => setActiveTab('phone')}
          >
            📱 Mobile OTP Login
          </button>
        </div>
      </div>

      <div aria-live="polite">
        {error && (
          <Alert tone="error" title={t('state.error.title')}>
            <p>{error}</p>
          </Alert>
        )}
      </div>

      {busy ? (
        <LoadingState />
      ) : activeTab === 'instant' && auth.step === 'phone' ? (
        <div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
              gap: 'var(--space-4)',
              marginBottom: 'var(--space-6)',
            }}
          >
            {DEMO_ACCOUNTS.map((acc) => (
              <div
                key={acc.role}
                className="card card--interactive anim-slide-up"
                style={{
                  padding: 'var(--space-5)',
                  borderRadius: 'var(--radius-xl)',
                  border: '2px solid var(--color-border)',
                  background: 'var(--color-surface)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  boxShadow: 'var(--shadow-card)',
                }}
                onClick={() => handleDemoLogin(acc)}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-3)' }}>
                    <span style={{ fontSize: '38px', lineHeight: 1 }}>{acc.icon}</span>
                    <Badge tone={acc.role === 'farmer' ? 'success' : acc.role === 'buyer' ? 'info' : 'gold'}>
                      {acc.badge}
                    </Badge>
                  </div>

                  <h3 style={{ margin: '0 0 4px', fontSize: 'var(--font-size-lg)', color: 'var(--color-brand-strong)' }}>
                    {acc.name}
                  </h3>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginBottom: 'var(--space-2)' }}>
                    📍 {acc.location}
                  </div>
                  <p className="text-body-sm muted" style={{ lineHeight: 1.5, margin: 0 }}>
                    {acc.description}
                  </p>
                </div>

                <div style={{ marginTop: 'var(--space-4)' }}>
                  <Button
                    variant={acc.role === 'farmer' ? 'primary' : 'secondary'}
                    className="btn--sm"
                    style={{ width: '100%', fontWeight: 700 }}
                  >
                    Log In as {acc.badge.split(' ')[0]} →
                  </Button>
                </div>
              </div>
            ))}
          </div>

          <div
            style={{
              textAlign: 'center',
              padding: 'var(--space-4)',
              background: 'var(--color-surface-alt)',
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--color-border-subtle)',
            }}
          >
            <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)' }}>
              Want to use your real phone number?{' '}
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                style={{ color: 'var(--color-brand)', fontWeight: 700 }}
                onClick={() => setActiveTab('phone')}
              >
                Switch to Mobile OTP Login →
              </button>
            </span>
          </div>
        </div>
      ) : auth.step === 'phone' ? (
        <form onSubmit={submitPhone} className="stack" style={{ maxWidth: 440, margin: '0 auto' }} noValidate>
          <div className="card" style={{ padding: 'var(--space-5)' }}>
            <h2 style={{ margin: '0 0 var(--space-2)' }}>{t('auth.signIn.title')}</h2>
            <p className="lede" style={{ marginBottom: 'var(--space-4)' }}>{t('auth.signIn.subtitle')}</p>
            <TextField
              id="phone"
              type="tel"
              inputMode="numeric"
              autoComplete="tel"
              label={t('auth.phone.label')}
              hint={t('auth.phone.hint')}
              placeholder={t('auth.phone.placeholder')}
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              required
            />
            <div className="inline-actions" style={{ marginTop: 'var(--space-4)' }}>
              <Button type="submit" variant="primary" style={{ width: '100%' }}>
                {t('auth.phone.sendCode')} →
              </Button>
            </div>
            <div style={{ marginTop: 'var(--space-3)', textAlign: 'center' }}>
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                onClick={() => setActiveTab('instant')}
              >
                ← Back to 1-Click Role Login
              </button>
            </div>
          </div>
        </form>
      ) : auth.step === 'otp' ? (
        <form onSubmit={submitCode} className="stack" style={{ maxWidth: 440, margin: '0 auto' }} noValidate>
          <div className="card" style={{ padding: 'var(--space-5)' }}>
            <h2 style={{ margin: '0 0 var(--space-2)' }}>{t('auth.otp.title')}</h2>
            <p className="lede" style={{ marginBottom: 'var(--space-4)' }}>
              {t('auth.otp.subtitle', { seconds: 5, phone: auth.maskedPhone ?? '' })}
            </p>

            {auth.devCode && (
              <Alert tone="info" title={t('auth.otp.devCodeNotice')}>
                <p>
                  <strong>{auth.devCode}</strong>
                </p>
              </Alert>
            )}

            <TextField
              id="otp"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={8}
              label={t('auth.otp.label')}
              hint={t('auth.otp.hint', { length: 6 })}
              value={code}
              onChange={(event) => setCode(event.target.value)}
              required
            />
            <div className="inline-actions" style={{ marginTop: 'var(--space-4)' }}>
              <Button type="submit" variant="primary" style={{ width: '100%' }}>
                {t('auth.otp.verify')} →
              </Button>
            </div>
            <div style={{ marginTop: 'var(--space-3)', textAlign: 'center' }}>
              <button type="button" className="btn btn--ghost btn--sm" onClick={auth.reset}>
                {t('auth.otp.changeNumber')}
              </button>
            </div>
          </div>
        </form>
      ) : auth.step === 'role' ? (
        <div className="stack" style={{ maxWidth: 560, margin: '0 auto' }}>
          <h2 style={{ textAlign: 'center', margin: '0 0 var(--space-2)' }}>{t('auth.role.title')}</h2>
          <p className="lede" style={{ textAlign: 'center', marginBottom: 'var(--space-4)' }}>{t('auth.role.subtitle')}</p>
          <div className="card-grid">
            {ROLE_OPTIONS.map((option) => (
              <button
                key={option.role}
                type="button"
                className="role-option"
                onClick={() => void run(() => auth.chooseRole(option.role))}
              >
                <span className="role-option__title">{t(option.labelKey)}</span>
                <span className="role-option__hint">{t(option.hintKey)}</span>
              </button>
            ))}
          </div>
        </div>
      ) : auth.step === 'onboarding' ? (
        <form onSubmit={submitOnboarding} className="stack" style={{ maxWidth: 440, margin: '0 auto' }} noValidate>
          <div className="card" style={{ padding: 'var(--space-5)' }}>
            <h2 style={{ margin: '0 0 var(--space-2)' }}>{t('auth.onboarding.title')}</h2>
            <p className="lede" style={{ marginBottom: 'var(--space-4)' }}>{t('auth.onboarding.subtitle')}</p>
            <TextField
              id="display-name"
              autoComplete="name"
              label={t('auth.onboarding.name')}
              placeholder={t('auth.onboarding.namePlaceholder')}
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              required
            />
            <div className="inline-actions" style={{ marginTop: 'var(--space-4)' }}>
              <Button type="submit" variant="primary" style={{ width: '100%' }}>
                {t('auth.onboarding.finish')} →
              </Button>
            </div>
          </div>
        </form>
      ) : null}
    </div>
  )
}
