import { useTranslation } from '../i18n/useTranslation'
import { navigate } from '../router'
import { Button } from '../components/ui'

export function NotFoundPage() {
  const { t } = useTranslation()

  return (
    <div className="container anim-fade-in" style={{ maxWidth: 640, margin: 'var(--space-10) auto', textAlign: 'center' }}>
      <div className="card" style={{ padding: 'var(--space-8)' }}>
        <img
          src="/logo.png"
          alt="AgriPredict Logo"
          width={72}
          height={72}
          style={{ borderRadius: '16px', margin: '0 auto var(--space-4)', display: 'block', boxShadow: '0 4px 14px rgba(0,0,0,0.15)' }}
        />
        <h1 className="text-title-xl" style={{ margin: '0 0 var(--space-2)' }}>{t('error.notFound.title')}</h1>
        <p className="text-body-md muted" style={{ margin: '0 0 var(--space-6)' }}>{t('error.notFound.body')}</p>

        <div className="flex-center flex-wrap flex-gap-2" style={{ justifyContent: 'center' }}>
          <Button variant="primary" onClick={() => navigate('/')}>
            🏠 {t('error.notFound.home')}
          </Button>
          <Button variant="secondary" onClick={() => navigate('/market')}>
            📊 Live Mandi Rates
          </Button>
          <Button variant="secondary" onClick={() => navigate('/chat')}>
            🎙️ Ask AgriMitra AI
          </Button>
        </div>
      </div>
    </div>
  )
}
