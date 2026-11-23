import { useState } from 'react'
import { useLocationContext, type AgriculturalHub } from '../context/LocationContext'
import { useTranslation } from '../i18n/useTranslation'
import { Badge } from './ui'

export function LocationBar() {
  const { activeHub, setActiveHubId, hubs } = useLocationContext()
  const { locale } = useTranslation()
  const [modalOpen, setModalOpen] = useState(false)

  const displayName =
    locale === 'hi' ? activeHub.nameHi : locale === 'te' ? activeHub.nameTe : activeHub.name

  return (
    <>
      <div
        className="location-strip"
        style={{
          background: 'linear-gradient(90deg, #10322a 0%, #174a3c 100%)',
          color: '#ffffff',
          borderBottom: '1px solid rgba(255, 255, 255, 0.12)',
          padding: '6px 16px',
          fontSize: '12px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '8px',
          position: 'sticky',
          top: '3.5rem',
          zIndex: 19,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}>
            <span style={{ color: '#E9B949' }}>📍</span>
            <span style={{ opacity: 0.85 }}>Active Mandi Hub:</span>
          </span>

          <button
            type="button"
            onClick={() => setModalOpen(true)}
            style={{
              background: 'rgba(233, 185, 73, 0.2)',
              border: '1px solid #E9B949',
              color: '#ffffff',
              padding: '3px 12px',
              borderRadius: '999px',
              fontWeight: 700,
              fontSize: '12px',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'var(--transition-fast)',
            }}
          >
            <span>{activeHub.icon}</span>
            <span>{displayName}</span>
            <span style={{ opacity: 0.8, fontSize: '11px' }}>({activeHub.primaryMandi})</span>
            <span style={{ fontSize: '10px', color: '#E9B949' }}>▼ Change</span>
          </button>

          <span style={{ opacity: 0.5 }}>|</span>

          <span style={{ opacity: 0.85, fontSize: '11px' }}>
            Zone: <strong>{activeHub.district}, {activeHub.state}</strong> · Dominant Crop: <strong>{activeHub.dominantCrop}</strong>
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Badge tone="gold" className="badge--pulse">
            <span className="pulse-dot" style={{ background: '#E9B949' }} />
            <span>AI Real-time Context Synced</span>
          </Badge>
        </div>
      </div>

      {/* Location Picker Modal */}
      {modalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.65)',
            backdropFilter: 'blur(4px)',
            zIndex: 99999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '16px',
          }}
          onClick={() => setModalOpen(false)}
        >
          <div
            className="anim-scale-in"
            style={{
              background: 'var(--color-surface)',
              borderRadius: 'var(--radius-xl)',
              maxWidth: '680px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              border: '2px solid var(--color-brand)',
              boxShadow: 'var(--shadow-xl)',
              padding: 'var(--space-5)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-3)' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 'var(--font-size-lg)', color: 'var(--color-brand-strong)' }}>
                  📍 Select Your Agricultural Region (अपना जिला / मंडी चुनें)
                </h3>
                <p className="text-body-sm muted" style={{ margin: '4px 0 0' }}>
                  All market prices, weather advisories, 10-day forecasts, and transport rates will automatically adapt to your chosen location.
                </p>
              </div>
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                onClick={() => setModalOpen(false)}
                style={{ fontSize: '18px', padding: '4px 8px' }}
              >
                ✕
              </button>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: 'var(--space-3)',
                marginTop: 'var(--space-4)',
              }}
            >
              {hubs.map((hub: AgriculturalHub) => {
                const isSelected = hub.id === activeHub.id
                const title = locale === 'hi' ? hub.nameHi : locale === 'te' ? hub.nameTe : hub.name

                return (
                  <button
                    key={hub.id}
                    type="button"
                    onClick={() => {
                      setActiveHubId(hub.id)
                      setModalOpen(false)
                    }}
                    style={{
                      textAlign: 'left',
                      padding: 'var(--space-3)',
                      borderRadius: 'var(--radius-lg)',
                      border: isSelected ? '2px solid var(--color-brand)' : '1px solid var(--color-border)',
                      background: isSelected ? 'var(--color-surface-alt)' : 'var(--color-surface)',
                      cursor: 'pointer',
                      transition: 'all var(--transition-fast)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '18px' }}>{hub.icon}</span>
                      {isSelected ? (
                        <Badge tone="success">✓ Active Location</Badge>
                      ) : (
                        <span style={{ fontSize: '10px', color: 'var(--color-text-muted)' }}>{hub.state}</span>
                      )}
                    </div>
                    <strong style={{ fontSize: 'var(--font-size-md)', color: isSelected ? 'var(--color-brand-strong)' : 'var(--color-text)' }}>
                      {title}
                    </strong>
                    <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
                      🏛️ {hub.primaryMandi} · <strong>{hub.district}</strong>
                    </div>
                    <div style={{ fontSize: '10px', color: 'var(--color-brand)', fontWeight: 600, marginTop: '2px' }}>
                      {hub.tag}
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
