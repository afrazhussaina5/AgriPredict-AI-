export function AgriPredictLogo({
  size = 36,
  showWordmark = true,
  theme = 'dark',
}: {
  size?: number
  showWordmark?: boolean
  theme?: 'dark' | 'light'
}) {
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '10px', textDecoration: 'none' }}>
      <img
        src="/logo.png"
        alt="AgriPredict AI Logo"
        width={size}
        height={size}
        style={{
          width: `${size}px`,
          height: `${size}px`,
          borderRadius: `${Math.round(size * 0.22)}px`,
          objectFit: 'cover',
          flexShrink: 0,
          boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
        }}
      />

      {showWordmark && (
        <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span
              style={{
                fontSize: size >= 40 ? '20px' : '17px',
                fontWeight: 800,
                color: theme === 'light' ? 'var(--color-brand)' : '#FFFFFF',
                letterSpacing: '-0.02em',
              }}
            >
              AgriPredict
            </span>
            <span
              style={{
                background: '#E9B949',
                color: '#153F35',
                fontSize: '10px',
                fontWeight: 900,
                padding: '2px 5px',
                borderRadius: '4px',
                letterSpacing: '0.05em',
              }}
            >
              AI
            </span>
          </div>
          <span
            style={{
              fontSize: '9px',
              color: theme === 'light' ? 'var(--color-text-secondary)' : 'rgba(255,255,255,0.75)',
              letterSpacing: '0.06em',
              marginTop: '3px',
              fontWeight: 600,
            }}
          >
            SMART MARKETS 🌱 STRONGER FARMERS
          </span>
        </div>
      )}
    </div>
  )
}
