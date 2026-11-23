import { useCallback, useEffect, useState } from 'react'

import {
  fetchDistricts,
  fetchMandis,
  fetchReferenceStatus,
  fetchStates,
  type District,
  type Mandi,
  type ReferenceStatus,
  type State,
} from '../api/client'
import { SelectField } from '../components/fields'
import { Alert, Badge, Card } from '../components/ui'
import { EmptyState, ErrorState, LoadingState } from '../components/states'
import type { TranslationKey } from '../i18n/translations'
import { useTranslation } from '../i18n/useTranslation'

/* Cascading location browser: State -> District -> Mandi.
   Every row shows where its name came from. When nothing is imported the page
   says so plainly instead of showing empty dropdowns. */

type Loadable<T> = { status: 'idle' } | { status: 'loading' } | { status: 'ready'; data: T } | { status: 'error' }

const IDLE: Loadable<never> = { status: 'idle' }
const LOADING: Loadable<never> = { status: 'loading' }

const COUNT_KEYS: Array<[string, TranslationKey]> = [
  ['states', 'ref.entity.state'],
  ['districts', 'ref.entity.district'],
  ['mandis', 'ref.entity.mandi'],
  ['commodities', 'ref.entity.commodity'],
  ['units', 'ref.entity.unit'],
]

/** Show the localized name when a verified translation exists, else the original. */
function displayName(
  row: { name: string; name_hi: string | null; name_te: string | null },
  locale: string,
): string {
  if (locale === 'hi' && row.name_hi) return row.name_hi
  if (locale === 'te' && row.name_te) return row.name_te
  return row.name
}

export function ReferencePage() {
  const { t, locale } = useTranslation()

  const [status, setStatus] = useState<ReferenceStatus | null>(null)
  const [statusError, setStatusError] = useState(false)

  const [states, setStates] = useState<Loadable<State[]>>(LOADING)
  const [districts, setDistricts] = useState<Loadable<District[]>>(IDLE)
  const [mandis, setMandis] = useState<Loadable<Mandi[]>>(IDLE)

  const [stateId, setStateId] = useState<number | null>(null)
  const [districtId, setDistrictId] = useState<number | null>(null)
  const [mandiId, setMandiId] = useState<number | null>(null)

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await fetchReferenceStatus())
      setStatusError(false)
    } catch {
      setStatusError(true)
    }
  }, [])

  const loadStates = useCallback(async () => {
    setStates(LOADING)
    try {
      setStates({ status: 'ready', data: await fetchStates() })
    } catch {
      setStates({ status: 'error' })
    }
  }, [])

  useEffect(() => {
    void loadStatus()
    void loadStates()
  }, [loadStatus, loadStates])

  // Changing a parent clears its children, so the cascade can never show a
  // district from a different state.
  async function onStateChange(next: number | null) {
    setStateId(next)
    setDistrictId(null)
    setMandiId(null)
    setDistricts(IDLE)
    setMandis(IDLE)
    if (next === null) return
    setDistricts(LOADING)
    try {
      setDistricts({ status: 'ready', data: await fetchDistricts(next) })
    } catch {
      setDistricts({ status: 'error' })
    }
  }

  async function onDistrictChange(next: number | null) {
    setDistrictId(next)
    setMandiId(null)
    setMandis(IDLE)
    if (next === null) return
    setMandis(LOADING)
    try {
      setMandis({ status: 'ready', data: await fetchMandis(next) })
    } catch {
      setMandis({ status: 'error' })
    }
  }

  if (statusError) {
    return (
      <ErrorState
        title={t('state.error.title')}
        body={t('state.error.body')}
        onRetry={() => {
          void loadStatus()
          void loadStates()
        }}
      />
    )
  }

  const stateRows = states.status === 'ready' ? states.data : []
  const districtRows = districts.status === 'ready' ? districts.data : []
  const mandiRows = mandis.status === 'ready' ? mandis.data : []
  const selectedMandi = mandiRows.find((mandi) => mandi.id === mandiId) ?? null

  return (
    <div className="stack anim-fade-in">
      <div>
        <h1>{t('ref.title')}</h1>
        <p className="lede">{t('ref.subtitle')}</p>
      </div>

      {status && !status.is_populated && (
        <Alert tone="info" title={t('ref.notPopulated.title')}>
          <p>{t('ref.notPopulated.body')}</p>
        </Alert>
      )}

      <Card title={t('ref.status.title')}>
        {status ? (
          <ul className="plain-list">
            {COUNT_KEYS.map(([entity, key]) => (
              <li key={entity}>{t('ref.status.counts', { entity: t(key), count: status.counts[entity] ?? 0 })}</li>
            ))}
          </ul>
        ) : (
          <LoadingState />
        )}
        {status && (
          <>
            <p className="muted">{t('ref.status.sources')}</p>
            {status.sources.length === 0 ? (
              <p className="muted">{t('ref.status.noSources')}</p>
            ) : (
              <ul className="plain-list">
                {status.sources.map((source) => (
                  <li key={source.id}>
                    {source.name}{' '}
                    <Badge tone={source.is_official ? 'success' : 'neutral'}>
                      {source.is_official ? t('ref.status.official') : t('ref.status.community')}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Card>

      <Card title={t('ref.title')}>
        {states.status === 'loading' && <LoadingState />}
        {states.status === 'error' && <ErrorState onRetry={() => void loadStates()} />}

        {states.status === 'ready' && stateRows.length === 0 && (
          <EmptyState title={t('ref.empty.states')} body={t('ref.notPopulated.body')} />
        )}

        {states.status === 'ready' && stateRows.length > 0 && (
          <div className="stack">
            <SelectField
              id="ref-state"
              label={t('ref.state.label')}
              value={stateId ?? ''}
              onChange={(event) =>
                void onStateChange(event.target.value ? Number(event.target.value) : null)
              }
            >
              <option value="">{t('ref.state.placeholder')}</option>
              {stateRows.map((row) => (
                <option key={row.id} value={row.id}>
                  {displayName(row, locale)}
                </option>
              ))}
            </SelectField>

            {stateId === null ? (
              <p className="muted">{t('ref.pickStateFirst')}</p>
            ) : districts.status === 'loading' ? (
              <LoadingState />
            ) : districts.status === 'ready' && districtRows.length === 0 ? (
              <EmptyState title={t('ref.empty.districts')} />
            ) : (
              <SelectField
                id="ref-district"
                label={t('ref.district.label')}
                value={districtId ?? ''}
                onChange={(event) =>
                  void onDistrictChange(
                    event.target.value ? Number(event.target.value) : null,
                  )
                }
              >
                <option value="">{t('ref.district.placeholder')}</option>
                {districtRows.map((row) => (
                  <option key={row.id} value={row.id}>
                    {displayName(row, locale)}
                  </option>
                ))}
              </SelectField>
            )}

            {districtId === null && stateId !== null && (
              <p className="muted">{t('ref.pickDistrictFirst')}</p>
            )}

            {districtId !== null && mandis.status === 'loading' && <LoadingState />}

            {districtId !== null &&
              mandis.status === 'ready' &&
              mandiRows.length === 0 && (
                <EmptyState title={t('ref.empty.mandis')} />
              )}

            {districtId !== null && mandis.status === 'ready' && mandiRows.length > 0 && (
              <>
                <SelectField
                  id="ref-mandi"
                  label={t('ref.mandi.label')}
                  value={mandiId ?? ''}
                  onChange={(event) =>
                    setMandiId(event.target.value ? Number(event.target.value) : null)
                  }
                >
                  <option value="">{t('ref.mandi.placeholder')}</option>
                  {mandiRows.map((row) => (
                    <option key={row.id} value={row.id}>
                      {displayName(row, locale)}
                    </option>
                  ))}
                </SelectField>

                {selectedMandi && (
                  <p className="muted">
                    {t('ref.sourceOf', { source: selectedMandi.source_name })}
                  </p>
                )}
              </>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}