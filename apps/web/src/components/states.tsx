import { useTranslation } from '../i18n/useTranslation'
import { Button, Spinner } from './ui'

/* Shared UI patterns required by every phase:
   loading, empty, error and success states.
   Text comes from translation resources at call time. */

export function LoadingState({ label }: { label?: string }) {
  const { t } = useTranslation()
  const text = label ?? t('state.loading')
  return (
    <div className="state-block" role="status" aria-live="polite">
      <p className="state-block__body">
        <Spinner /> {text}
      </p>
    </div>
  )
}

export function EmptyState({
  title,
  body,
  action,
}: {
  title?: string
  body?: string
  action?: import('react').ReactNode
}) {
  const { t } = useTranslation()
  return (
    <div className="state-block">
      <h3 className="state-block__title">{title ?? t('state.empty.title')}</h3>
      <p className="state-block__body">{body ?? t('state.empty.body')}</p>
      {action && <div style={{ marginTop: 'var(--space-3)' }}>{action}</div>}
    </div>
  )
}

export function ErrorState({
  title,
  body,
  onRetry,
}: {
  title?: string
  body?: string
  onRetry?: () => void
}) {
  const { t } = useTranslation()
  return (
    <div className="state-block" role="alert">
      <h3 className="state-block__title">{title ?? t('state.error.title')}</h3>
      <p className="state-block__body">{body ?? t('state.error.body')}</p>
      {onRetry && (
        <p>
          <Button variant="secondary" onClick={onRetry}>
            {t('state.error.retry')}
          </Button>
        </p>
      )}
    </div>
  )
}

export function SuccessState({ title, body }: { title?: string; body?: string }) {
  const { t } = useTranslation()
  return (
    <div className="state-block" role="status">
      <h3 className="state-block__title">{title ?? t('state.success.title')}</h3>
      {body && <p className="state-block__body">{body}</p>}
    </div>
  )
}
