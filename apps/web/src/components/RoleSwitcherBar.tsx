import { navigate } from '../router'

export type AppUserRole = 'farmer' | 'transport' | 'storage' | 'buyer'

export function RoleSwitcherBar({ activeRole }: { activeRole: AppUserRole }) {
  const roles: Array<{
    id: AppUserRole
    icon: string
    titleEn: string
    titleHi: string
    desc: string
    to: string
  }> = [
    {
      id: 'farmer',
      icon: '👨‍🌾',
      titleEn: 'Farmer',
      titleHi: 'किसान / రైతు',
      desc: 'Sell vs Store decision, net returns, schemes',
      to: '/dashboard/farmer',
    },
    {
      id: 'transport',
      icon: '🚛',
      titleEn: 'Transporter',
      titleHi: 'ट्रांसपोर्टर / రవాణా',
      desc: 'Fleet availability, incoming load bids',
      to: '/dashboard/transport',
    },
    {
      id: 'storage',
      icon: '🏭',
      titleEn: 'Storage & Warehouse',
      titleHi: 'गोदाम / కోల్డ్ స్టోరేజ్',
      desc: 'Capacity meter, e-NWR receipts, release alerts',
      to: '/dashboard/storage',
    },
    {
      id: 'buyer',
      icon: '🤝',
      titleEn: 'Buyer & Trader',
      titleHi: 'व्यापारी / కొనుగోలుదారు',
      desc: 'Post procurement demands, browse harvest lots',
      to: '/dashboard/buyer',
    },
  ]

  return (
    <div
      style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border-default)',
        borderRadius: 'var(--radius-xl)',
        padding: 'var(--space-2) var(--space-3)',
        marginBottom: 'var(--space-5)',
        boxShadow: 'var(--shadow-sm)',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 'var(--space-2)',
          marginBottom: 'var(--space-2)',
          padding: '0 var(--space-2)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-brand)' }}>
            ⚡ ACTIVE USER WORKSPACE (उपयोगकर्ता चुनें):
          </span>
          <span className="text-caption muted">
            Switch between Farmer, Transporter, Warehouse, and Buyer dashboards
          </span>
        </div>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 'var(--space-2)',
        }}
      >
        {roles.map((r) => {
          const isActive = activeRole === r.id
          return (
            <button
              key={r.id}
              type="button"
              onClick={() => navigate(r.to)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-3)',
                padding: 'var(--space-2) var(--space-3)',
                borderRadius: 'var(--radius-lg)',
                border: isActive
                  ? '2px solid var(--color-brand)'
                  : '1px solid var(--color-border-subtle)',
                background: isActive ? 'var(--color-surface-alt)' : 'var(--color-surface)',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'var(--transition-fast)',
                boxShadow: isActive ? 'var(--shadow-card)' : 'none',
              }}
            >
              <span
                style={{
                  fontSize: '22px',
                  background: isActive ? 'var(--color-brand)' : 'var(--color-surface-muted)',
                  color: isActive ? '#FFFFFF' : 'inherit',
                  width: '40px',
                  height: '40px',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                {r.icon}
              </span>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <strong style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text)' }}>
                    {r.titleEn}
                  </strong>
                  <span style={{ fontSize: '10px', color: 'var(--color-brand)', fontWeight: 600 }}>
                    {r.titleHi}
                  </span>
                </div>
                <span
                  style={{
                    display: 'block',
                    fontSize: '10px',
                    color: 'var(--color-text-muted)',
                    lineHeight: 1.2,
                    marginTop: '2px',
                  }}
                >
                  {r.desc}
                </span>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
