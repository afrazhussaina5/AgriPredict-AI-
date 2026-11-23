import { useState, type ReactNode } from 'react'

import { useAuth } from '../auth/context'
import { useTranslation } from '../i18n/useTranslation'
import { useRoute } from '../router'
import { LanguageSwitcher } from './LanguageSwitcher'
import { LocationBar } from './LocationBar'
import { AgriPredictLogo } from './brand/AgriPredictLogo'

/* Premium application shell — dark forest-green header, sticky nav,
   responsive mobile menu with smooth slide, premium footer.
   Responsive: menu collapses behind a toggle below 720px. */

export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const path = useRoute()
  const { user, signOut } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)

  const primaryRole = user?.roles[0]

  const navItems = (() => {
    if (!user) {
      return [
        { to: '/', label: '🏠 Home' },
        { to: '/analyze', label: '💡 Crop Analysis & Advice' },
        { to: '/market', label: '📊 ' + t('nav.market') },
        { to: '/forecast', label: '📈 10-Day Forecast' },
        { to: '/compare', label: '⚖️ ' + t('nav.compare') },
        { to: '/chat', label: '🤖 AgriMitra AI' },
        { to: '/schemes', label: '🏛️ ' + t('nav.schemes') },
        { to: '/buyers', label: '🤝 ' + t('nav.buyers') },
        { to: '/services', label: '🚛 ' + t('nav.services') },
      ]
    }

    if (primaryRole === 'buyer') {
      return [
        { to: '/dashboard', label: t('nav.dashboard') },
        { to: '/analyze', label: '💡 Crop Analysis' },
        { to: '/buyers', label: '🤝 ' + t('nav.buyers') },
        { to: '/market', label: '📊 ' + t('nav.market') },
        { to: '/profile', label: t('nav.profile') },
      ]
    }

    if (primaryRole === 'transport_provider') {
      return [
        { to: '/dashboard', label: t('nav.dashboard') },
        { to: '/analyze', label: '💡 Freight Rates' },
        { to: '/services', label: '🚛 ' + t('nav.services') },
        { to: '/market', label: '📊 ' + t('nav.market') },
        { to: '/profile', label: t('nav.profile') },
      ]
    }

    if (primaryRole === 'storage_provider') {
      return [
        { to: '/dashboard', label: t('nav.dashboard') },
        { to: '/analyze', label: '💡 Storage Trends' },
        { to: '/services', label: '🏭 ' + t('nav.services') },
        { to: '/market', label: '📊 ' + t('nav.market') },
        { to: '/profile', label: t('nav.profile') },
      ]
    }

    if (primaryRole === 'admin') {
      return [
        { to: '/dashboard', label: t('nav.dashboard') },
        { to: '/analyze', label: '💡 Crop Analysis' },
        { to: '/reference', label: t('ref.title') },
        { to: '/market', label: '📊 ' + t('nav.market') },
        { to: '/schemes', label: '🏛️ ' + t('nav.schemes') },
        { to: '/profile', label: t('nav.profile') },
      ]
    }

    // Default: Farmer
    return [
      { to: '/dashboard', label: t('nav.dashboard') },
      { to: '/analyze', label: '💡 When, Where & Who' },
      { to: '/market', label: '📊 ' + t('nav.market') },
      { to: '/forecast', label: '📈 10-Day Forecast' },
      { to: '/compare', label: '⚖️ ' + t('nav.compare') },
      { to: '/chat', label: '🤖 AgriMitra AI' },
      { to: '/schemes', label: '🏛️ ' + t('nav.schemes') },
      { to: '/buyers', label: '🤝 ' + t('nav.buyers') },
      { to: '/services', label: '🚛 ' + t('nav.services') },
      { to: '/lots', label: t('nav.myProduce') },
      { to: '/profile', label: t('nav.profile') },
    ]
  })()

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        {t('common.skipToContent')}
      </a>

      <header className="app-header">
        <div className="app-header__bar">
          {/* Brand */}
          <a
            className="app-brand"
            href="#/"
            onClick={() => setMenuOpen(false)}
            aria-label={t('common.brandName')}
          >
            <AgriPredictLogo size={36} />
          </a>

          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            {/* Mobile menu toggle */}
            <button
              type="button"
              className="btn btn--ghost app-nav__toggle"
              style={{ color: '#ffffff', border: '1px solid rgba(255,255,255,0.25)' }}
              aria-expanded={menuOpen}
              aria-controls="primary-nav"
              onClick={() => setMenuOpen((open) => !open)}
            >
              {menuOpen ? '✕' : '☰'}
            </button>
          </div>

          {/* Nav */}
          <nav
            id="primary-nav"
            className="app-nav"
            data-open={menuOpen}
            aria-label={t('common.brandName')}
          >
            {navItems.map((item) => (
              <a
                key={item.to}
                className="app-nav__link"
                href={`#${item.to}`}
                aria-current={
                  path === item.to || (item.to !== '/' && path.startsWith(`${item.to}/`))
                    ? 'page'
                    : undefined
                }
                onClick={() => setMenuOpen(false)}
              >
                {item.label}
              </a>
            ))}
            {user !== null && (
              <button
                type="button"
                className="btn btn--ghost app-nav__link"
                style={{ color: 'rgba(255,255,255,0.85)', fontSize: 'var(--font-size-sm)' }}
                onClick={() => {
                  setMenuOpen(false)
                  void signOut()
                }}
              >
                {t('auth.signOut')}
              </button>
            )}
            {!user && (
              <a
                href="#/signin"
                className="btn btn--sm"
                style={{
                  background: '#E9B949',
                  color: '#153F35',
                  fontWeight: 700,
                  borderRadius: 'var(--radius-pill)',
                  padding: '6px 16px',
                  textDecoration: 'none',
                  fontSize: 'var(--font-size-sm)',
                }}
                onClick={() => setMenuOpen(false)}
              >
                Sign In
              </a>
            )}
            <LanguageSwitcher />
          </nav>
        </div>
      </header>

      <LocationBar />

      <main id="main-content" className="app-main" tabIndex={-1}>
        {children}
      </main>

      <footer className="app-footer">
        <div style={{ maxWidth: '72rem', margin: '0 auto', padding: 'var(--space-6) var(--space-4)' }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: 'var(--space-6)',
              marginBottom: 'var(--space-6)',
            }}
          >
            <div>
              <div style={{ marginBottom: 'var(--space-3)' }}>
                <AgriPredictLogo size={32} />
              </div>
              <p style={{ fontSize: '12px', opacity: 0.6, lineHeight: 1.6, margin: 0 }}>
                Real-time mandi intelligence, 10-day ML price forecasts, and farmer decision support for India's agricultural markets.
              </p>
            </div>
            <div>
              <div style={{ fontWeight: 600, color: '#E9B949', marginBottom: 'var(--space-2)', fontSize: '12px', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                Market Tools
              </div>
              {[
                { href: '#/market', label: 'Live Mandi Prices' },
                { href: '#/forecast', label: '10-Day ML Forecast' },
                { href: '#/compare', label: 'Net Return Calculator' },
                { href: '#/chat', label: 'AgriMitra Voice AI' },
              ].map((l) => (
                <a key={l.href} href={l.href} style={{ display: 'block', color: 'rgba(255,255,255,0.6)', fontSize: '12px', marginBottom: '6px', textDecoration: 'none' }}>
                  {l.label}
                </a>
              ))}
            </div>
            <div>
              <div style={{ fontWeight: 600, color: '#E9B949', marginBottom: 'var(--space-2)', fontSize: '12px', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                Role Dashboards
              </div>
              {[
                { href: '#/dashboard/farmer', label: '👨‍🌾 Farmer Workspace' },
                { href: '#/dashboard/transport', label: '🚛 Transporter' },
                { href: '#/dashboard/storage', label: '🏭 Warehouse Owner' },
                { href: '#/dashboard/buyer', label: '🤝 Buyer & Trader' },
              ].map((l) => (
                <a key={l.href} href={l.href} style={{ display: 'block', color: 'rgba(255,255,255,0.6)', fontSize: '12px', marginBottom: '6px', textDecoration: 'none' }}>
                  {l.label}
                </a>
              ))}
            </div>
            <div>
              <div style={{ fontWeight: 600, color: '#E9B949', marginBottom: 'var(--space-2)', fontSize: '12px', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                Resources
              </div>
              {[
                { href: '#/schemes', label: '🏛️ Government Schemes' },
                { href: '#/buyers', label: '🤝 Buyer Marketplace' },
                { href: '#/services', label: '🚚 Transport & Storage' },
              ].map((l) => (
                <a key={l.href} href={l.href} style={{ display: 'block', color: 'rgba(255,255,255,0.6)', fontSize: '12px', marginBottom: '6px', textDecoration: 'none' }}>
                  {l.label}
                </a>
              ))}
            </div>
          </div>
          <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: 'var(--space-4)', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--space-2)', alignItems: 'center' }}>
            <p style={{ fontSize: '11px', opacity: 0.5, margin: 0 }}>
              {t('common.footerText')} · Prices are indicative, not official government valuations.
            </p>
            <p style={{ fontSize: '11px', opacity: 0.5, margin: 0 }}>
              Data: Agmarknet / APMC · ML: Ridge Regression Benchmark
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
