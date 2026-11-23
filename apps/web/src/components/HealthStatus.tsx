import { useCallback, useEffect, useState } from 'react'

import { useTranslation } from '../i18n/useTranslation'
import { Button, Spinner } from './ui'

/* Shows the REAL backend health state. It never fabricates a status:
   loading -> success or error, straight from GET /api/v1/health. */

type HealthState =
  | { status: 'loading' }
  | { status: 'success'; version: string; environment: string }
  | { status: 'error'; message: string }

export function HealthStatus() {
  const { t } = useTranslation()
  const [health, setHealth] = useState<HealthState>({ status: 'loading' })

  const check = useCallback(async () => {
    setHealth({ status: 'loading' })
    try {
      const response = await fetch('/api/v1/health')
      if (!response.ok) {
        throw new Error(`API responded with status ${response.status}`)
      }
      const data = (await response.json()) as {
        status: string
        version: string
        environment: string
      }
      if (data.status !== 'ok') {
        throw new Error('API reported an unhealthy status')
      }
      setHealth({ status: 'success', version: data.version, environment: data.environment })
    } catch (error: unknown) {
      setHealth({
        status: 'error',
        message: error instanceof Error ? error.message : 'unknown error',
      })
    }
  }, [])

  useEffect(() => {
    void check()
  }, [check])

  return (
    <div className="stack">
      <p
        className={`status-line status-line--${
          health.status === 'success'
            ? 'success'
            : health.status === 'error'
              ? 'error'
              : 'loading'
        }`}
        role="status"
        aria-live="polite"
      >
        {health.status === 'loading' && (
          <>
            <Spinner /> {t('landing.status.checking')}
          </>
        )}
        {health.status === 'success' &&
          t('landing.status.ok', {
            version: health.version,
            environment: health.environment,
          })}
        {health.status === 'error' && t('landing.status.error', { message: health.message })}
      </p>
      {health.status === 'error' && (
        <p>
          <Button variant="secondary" onClick={() => void check()}>
            {t('landing.status.retry')}
          </Button>
        </p>
      )}
    </div>
  )
}
