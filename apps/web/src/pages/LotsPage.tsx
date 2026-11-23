import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  ApiError,
  archiveLot,
  changeLotStatus,
  createLot,
  fetchCommodities,
  fetchGrades,
  fetchLot,
  fetchMyLots,
  fetchUnits,
  fetchVarieties,
  updateLot,
  type Commodity,
  type Grade,
  type Lot,
  type LotDetail,
  type LotInput,
  type LotStatus,
  type Unit,
  type Variety,
} from '../api/client'
import { useAuth } from '../auth/context'
import { CheckboxField, SelectField, TextField } from '../components/fields'
import { EmptyState, ErrorState, LoadingState } from '../components/states'
import { Alert, Badge, Button, Card } from '../components/ui'
import {
  displayReferenceName,
  useLocationCascade,
} from '../components/useLocationCascade'
import { useTranslation } from '../i18n/useTranslation'
import { useLocationContext } from '../context/LocationContext'

/* The farmer's own produce lots: list, create, edit and move through the
   lifecycle.

   Built from the existing design system only - Card, Badge, Alert, Button
   (including .btn--sm for row actions), .table-wrap/.table for the list,
   .inline-actions for button groups and CheckboxField for the visibility
   opt-ins. No page-specific CSS.

   Two rules are surfaced rather than hidden:
   * A lot is created as a draft. Publishing is a separate, deliberate action.
   * "What buyers can see" is part of the form, and every toggle starts off. */

type Draft = {
  commodityId: number | null
  varietyId: number | null
  gradeId: number | null
  quantity: string
  unitId: number | null
  readyDate: string
  pickupAreaLabel: string
  expectedPrice: string
  minPrice: string
  notes: string
  showExpectedPrice: boolean
  showPickupArea: boolean
  showNotes: boolean
}

const EMPTY_DRAFT: Draft = {
  commodityId: null,
  varietyId: null,
  gradeId: null,
  quantity: '',
  unitId: null,
  readyDate: '',
  pickupAreaLabel: '',
  expectedPrice: '',
  minPrice: '',
  notes: '',
  showExpectedPrice: false,
  showPickupArea: false,
  showNotes: false,
}

const STATUS_ORDER: LotStatus[] = ['published', 'paused', 'draft', 'closed', 'archived']

const STATUS_KEY = {
  draft: 'lot.statusDraft',
  published: 'lot.statusPublished',
  paused: 'lot.statusPaused',
  closed: 'lot.statusClosed',
  archived: 'lot.statusArchived',
} as const

const STATUS_TONE = {
  draft: 'neutral',
  published: 'success',
  paused: 'warning',
  closed: 'info',
  archived: 'neutral',
} as const

const STATUS_COUNT_KEY = {
  draft: 'lot.statusDraft',
  published: 'lot.statusPublished',
  paused: 'lot.statusPaused',
  closed: 'lot.statusClosed',
  archived: 'lot.statusArchived',
} as const

/** The server decides legality; the client just asks for a move. */
const RESUME_FROM: Partial<Record<LotStatus, LotStatus>> = { paused: 'published' }
const PAUSE_FROM: Partial<Record<LotStatus, LotStatus>> = { published: 'paused' }

/** A reference row that can be joined to recover a localized name. */
type Named = { id: number; name: string; name_hi: string | null; name_te: string | null }

/**
 * The API returns the official English name on a lot, but the farmer may be
 * reading in Hindi or Telugu. The reference lists are already loaded for the
 * form, so join against them rather than sending duplicate localized columns
 * on every lot response.
 */
function lookupLocalized<T extends Named>(
  rows: T[],
  id: number | null,
  fallback: string | null,
  locale: string,
): string | null {
  if (id === null) return fallback
  const row = rows.find((candidate) => candidate.id === id)
  if (!row) return fallback
  if (locale === 'hi' && row.name_hi) return row.name_hi
  if (locale === 'te' && row.name_te) return row.name_te
  return row.name
}

function draftFromLot(lot: Lot): Draft {
  return {
    commodityId: lot.commodity_id,
    varietyId: lot.variety_id,
    gradeId: lot.grade_id,
    quantity: lot.quantity,
    unitId: lot.unit_id,
    readyDate: lot.ready_date,
    pickupAreaLabel: lot.pickup_area_label ?? '',
    expectedPrice: lot.expected_price_per_unit ?? '',
    minPrice: lot.min_expected_price_per_unit ?? '',
    notes: lot.notes ?? '',
    showExpectedPrice: lot.show_expected_price,
    showPickupArea: lot.show_pickup_area,
    showNotes: lot.show_notes,
  }
}

export function LotsPage() {
  const { t, locale } = useTranslation()
  const { user } = useAuth()
  const { activeHub } = useLocationContext()

  const [lots, setLots] = useState<Lot[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [detail, setDetail] = useState<LotDetail | null>(null)

  const [editing, setEditing] = useState<Lot | null>(null)
  const [creating, setCreating] = useState(false)
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT)
  const [saving, setSaving] = useState(false)

  const [commodities, setCommodities] = useState<Commodity[]>([])
  const [units, setUnits] = useState<Unit[]>([])
  const [varieties, setVarieties] = useState<Variety[]>([])
  const [grades, setGrades] = useState<Grade[]>([])

  const location = useLocationCascade()

  const signedIn = user !== null
  const isFarmer = user?.roles.includes('farmer') ?? false

  const loadLots = useCallback(async () => {
    setLoading(true)
    try {
      const page = await fetchMyLots({ limit: 100 })
      setLots(page.items)
      setLoadError(false)
    } catch {
      setLoadError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!signedIn) {
      setLoading(false)
      return
    }
    void loadLots()
  }, [signedIn, loadLots])

  // Reference lists for the form. If nothing is imported the page says so
  // rather than showing empty dropdowns.
  useEffect(() => {
    if (!signedIn) return
    void (async () => {
      try {
        const [cropList, unitList] = await Promise.all([fetchCommodities(), fetchUnits()])
        setCommodities(cropList)
        setUnits(unitList)
      } catch {
        setCommodities([])
        setUnits([])
      }
    })()
  }, [signedIn])

  useEffect(() => {
    // Only ask once a crop is chosen: the endpoint is keyed by a real id, so
    // requesting with 0 only produced a 404.
    if (!draft.commodityId) {
      setVarieties([])
      return
    }
    void (async () => {
      try {
        setVarieties(await fetchVarieties(draft.commodityId as number))
      } catch {
        setVarieties([])
      }
    })()
  }, [draft.commodityId])

  useEffect(() => {
    void (async () => {
      try {
        setGrades(await fetchGrades(draft.commodityId ?? undefined))
      } catch {
        setGrades([])
      }
    })()
  }, [draft.commodityId])

  const patch = useCallback((changes: Partial<Draft>) => {
    setDraft((current) => ({ ...current, ...changes }))
  }, [])

  const startCreate = useCallback(() => {
    setCreating(true)
    setEditing(null)
    setDetail(null)
    setDraft({ ...EMPTY_DRAFT, readyDate: new Date().toISOString().slice(0, 10) })
    setActionError(null)
  }, [])

  const startEdit = useCallback((lot: Lot) => {
    setEditing(lot)
    setCreating(false)
    setDetail(null)
    setDraft(draftFromLot(lot))
    setActionError(null)
    // The pickup cascade is deliberately not prefilled: re-picking the state is
    // quick, and inferring a parent from a child id would be fragile.
  }, [])

  const cancelForm = useCallback(() => {
    setCreating(false)
    setEditing(null)
    setDraft(EMPTY_DRAFT)
  }, [])

  const showHistory = useCallback(async (lot: Lot) => {
    setActionError(null)
    try {
      setDetail(await fetchLot(lot.id))
    } catch (error) {
      setActionError(error instanceof ApiError ? error.message : t('state.error.body'))
    }
  }, [t])

  const canSubmit = useMemo(
    () =>
      draft.commodityId !== null &&
      draft.unitId !== null &&
      Number(draft.quantity) > 0 &&
      draft.readyDate !== '',
    [draft],
  )

  const counts = useMemo(() => {
    const tally: Record<string, number> = {}
    for (const lot of lots) tally[lot.status] = (tally[lot.status] ?? 0) + 1
    return tally
  }, [lots])

  async function onSave() {
    if (!canSubmit) return
    setSaving(true)
    setActionError(null)

    const payload: LotInput = {
      commodity_id: draft.commodityId as number,
      variety_id: draft.varietyId,
      grade_id: draft.gradeId,
      quantity: draft.quantity,
      unit_id: draft.unitId as number,
      ready_date: draft.readyDate,
      pickup_district_id: location.districtId,
      pickup_mandi_id: location.mandiId,
      pickup_area_label: draft.pickupAreaLabel || null,
      expected_price_per_unit: draft.expectedPrice || null,
      min_expected_price_per_unit: draft.minPrice || null,
      notes: draft.notes || null,
      show_expected_price: draft.showExpectedPrice,
      show_pickup_area: draft.showPickupArea,
      show_notes: draft.showNotes,
    }

    try {
      if (editing) {
        await updateLot(editing.id, payload)
        setNotice(t('lot.updated'))
      } else {
        await createLot(payload)
        setNotice(t('lot.saved'))
      }
      cancelForm()
      await loadLots()
    } catch (error) {
      setActionError(error instanceof ApiError ? error.message : t('state.error.body'))
    } finally {
      setSaving(false)
    }
  }

  async function onMove(lot: Lot, next: LotStatus) {
    setBusyId(lot.id)
    setActionError(null)
    try {
      await changeLotStatus(lot.id, next)
      await loadLots()
    } catch (error) {
      setActionError(error instanceof ApiError ? error.message : t('state.error.body'))
    } finally {
      setBusyId(null)
    }
  }

  async function onArchive(lot: Lot) {
    setBusyId(lot.id)
    setActionError(null)
    try {
      await archiveLot(lot.id)
      await loadLots()
    } catch (error) {
      setActionError(error instanceof ApiError ? error.message : t('state.error.body'))
    } finally {
      setBusyId(null)
    }
  }

  if (!signedIn) {
    return (
      <div className="stack">
        <div>
          <h1>{t('lot.title')}</h1>
          <p className="lede">{t('lot.subtitle')}</p>
        </div>
        <Card>
          <EmptyState title={t('lot.signInTitle')} body={t('lot.signInBody')} />
          <div className="inline-actions">
            <a className="btn btn--primary" href="#/signin">
              {t('auth.signIn.title')}
            </a>
          </div>
        </Card>
      </div>
    )
  }

  const formOpen = creating || editing !== null
  const referenceMissing = commodities.length === 0 || units.length === 0

  return (
    <div className="stack anim-fade-in">
      <div>
        <h1>{t('lot.title')}</h1>
        <p className="lede">{t('lot.subtitle')}</p>
      </div>

      <div className="alert alert--info">
        <div className="alert__body">
          <p className="alert__title">🌾 Optional Produce Listing (Farmer Choice)</p>
          <p className="text-sm muted">
            Listing your harvest is 100% voluntary. You can check daily mandi prices, compare logistics realization, and discover government welfare schemes without ever creating a listing.
          </p>
        </div>
      </div>

      {!isFarmer && (
        <Alert tone="warning" title={t('lot.title')}>
          <p>{t('lot.signInBody')}</p>
        </Alert>
      )}

      {notice && (
        <Alert tone="success">
          <p>{notice}</p>
        </Alert>
      )}
      {actionError && (
        <Alert tone="error" title={t('state.error.title')}>
          <p>{actionError}</p>
        </Alert>
      )}

      {!loading && lots.length > 0 && (
        <div className="card-grid">
          {STATUS_ORDER.filter((status) => (counts[status] ?? 0) > 0).map((status) => (
            <Card key={status}>
              <p className="muted">{t(STATUS_COUNT_KEY[status])}</p>
              <h2>{counts[status]}</h2>
            </Card>
          ))}
        </div>
      )}

      {isFarmer && formOpen && (
        <Card title={t(editing ? 'lot.editTitle' : 'lot.createTitle')}>
          {referenceMissing ? (
            <Alert tone="info" title={t('ref.notPopulated.title')}>
              <p>{t('ref.notPopulated.body')}</p>
            </Alert>
          ) : (
            <div className="stack">
              <h3>{t('lot.form.what')}</h3>
              <SelectField
                id="lot-commodity"
                label={t('lot.commodity')}
                value={draft.commodityId ?? ''}
                onChange={(event) =>
                  patch({
                    commodityId: event.target.value ? Number(event.target.value) : null,
                    varietyId: null,
                    gradeId: null,
                  })
                }
              >
                <option value="">{t('common.none')}</option>
                {commodities.map((row) => (
                  <option key={row.id} value={row.id}>
                    {displayReferenceName(row, locale)}
                  </option>
                ))}
              </SelectField>

              {varieties.length > 0 && (
                <SelectField
                  id="lot-variety"
                  label={t('lot.variety')}
                  value={draft.varietyId ?? ''}
                  onChange={(event) =>
                    patch({ varietyId: event.target.value ? Number(event.target.value) : null })
                  }
                >
                  <option value="">{t('common.none')}</option>
                  {varieties.map((row) => (
                    <option key={row.id} value={row.id}>
                      {displayReferenceName(row, locale)}
                    </option>
                  ))}
                </SelectField>
              )}

              {grades.length > 0 && (
                <SelectField
                  id="lot-grade"
                  label={t('lot.grade')}
                  value={draft.gradeId ?? ''}
                  onChange={(event) =>
                    patch({ gradeId: event.target.value ? Number(event.target.value) : null })
                  }
                >
                  <option value="">{t('common.none')}</option>
                  {grades.map((row) => (
                    <option key={row.id} value={row.id}>
                      {displayReferenceName(row, locale)}
                    </option>
                  ))}
                </SelectField>
              )}

              <TextField
                id="lot-quantity"
                label={t('lot.quantity')}
                type="number"
                min="0"
                step="any"
                inputMode="decimal"
                value={draft.quantity}
                onChange={(event) => patch({ quantity: event.target.value })}
              />

              <SelectField
                id="lot-unit"
                label={t('lot.unit')}
                value={draft.unitId ?? ''}
                onChange={(event) =>
                  patch({ unitId: event.target.value ? Number(event.target.value) : null })
                }
              >
                <option value="">{t('common.none')}</option>
                {units.map((row) => (
                  <option key={row.id} value={row.id}>
                    {displayReferenceName(row, locale)}
                  </option>
                ))}
              </SelectField>

              <TextField
                id="lot-ready-date"
                label={t('lot.readyDate')}
                hint={t('lot.readyDateHelp')}
                type="date"
                value={draft.readyDate}
                onChange={(event) => patch({ readyDate: event.target.value })}
              />

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ margin: 0 }}>{t('lot.form.where')}</h3>
                <span className="text-caption muted">
                  📍 Active Region: <strong>{activeHub.district}, {activeHub.state}</strong>
                </span>
              </div>
              <SelectField
                id="lot-pickup-state"
                label={t('ref.state.label')}
                value={location.stateId ?? ''}
                onChange={(event) =>
                  location.setStateId(event.target.value ? Number(event.target.value) : null)
                }
              >
                <option value="">{t('common.none')}</option>
                {(location.states.status === 'ready' ? location.states.data : []).map((row) => (
                  <option key={row.id} value={row.id}>
                    {displayReferenceName(row, locale)}
                  </option>
                ))}
              </SelectField>

              {location.stateId !== null && location.districts.status === 'ready' && (
                <SelectField
                  id="lot-pickup-district"
                  label={t('ref.district.label')}
                  value={location.districtId ?? ''}
                  onChange={(event) =>
                    location.setDistrictId(
                      event.target.value ? Number(event.target.value) : null,
                    )
                  }
                >
                  <option value="">{t('common.none')}</option>
                  {(location.districts.status === 'ready' ? location.districts.data : []).map(
                    (row) => (
                      <option key={row.id} value={row.id}>
                        {displayReferenceName(row, locale)}
                      </option>
                    ),
                  )}
                </SelectField>
              )}

              {location.districtId !== null && location.mandis.status === 'ready' && (
                <SelectField
                  id="lot-pickup-mandi"
                  label={t('lot.pickupMandi')}
                  value={location.mandiId ?? ''}
                  onChange={(event) =>
                    location.setMandiId(
                      event.target.value ? Number(event.target.value) : null,
                    )
                  }
                >
                  <option value="">{t('common.none')}</option>
                  {(location.mandis.status === 'ready' ? location.mandis.data : []).map((row) => (
                    <option key={row.id} value={row.id}>
                      {displayReferenceName(row, locale)}
                    </option>
                  ))}
                </SelectField>
              )}

              <TextField
                id="lot-pickup-area"
                label={t('lot.pickupArea')}
                value={draft.pickupAreaLabel}
                onChange={(event) => patch({ pickupAreaLabel: event.target.value })}
              />

              <h3>{t('lot.form.price')}</h3>
              <SelectField
                id="lot-no-price"
                label={t('lot.priceNone')}
                hint={t('lot.priceNoneHelp')}
                value={draft.expectedPrice ? 'set' : 'none'}
                onChange={(event) =>
                  patch({ expectedPrice: event.target.value === 'set' ? '0' : '' })
                }
              >
                <option value="none">{t('lot.notStated')}</option>
                <option value="set">{t('lot.priceState')}</option>
              </SelectField>

              {draft.expectedPrice !== '' && (
                <>
                  <TextField
                    id="lot-expected-price"
                    label={t('lot.expectedPrice')}
                    type="number"
                    min="0"
                    step="any"
                    inputMode="decimal"
                    value={draft.expectedPrice}
                    onChange={(event) => patch({ expectedPrice: event.target.value })}
                  />
                  <TextField
                    id="lot-min-price"
                    label={t('lot.minPrice')}
                    type="number"
                    min="0"
                    step="any"
                    inputMode="decimal"
                    value={draft.minPrice}
                    onChange={(event) => patch({ minPrice: event.target.value })}
                  />
                </>
              )}

              <h3>{t('lot.form.visibility')}</h3>
              <CheckboxField
                id="lot-show-price"
                label={t('lot.visibilityPrice')}
                hint={t('lot.visibilityPriceHelp')}
                checked={draft.showExpectedPrice}
                disabled={!draft.expectedPrice}
                onChange={(event) => patch({ showExpectedPrice: event.target.checked })}
              />
              <CheckboxField
                id="lot-show-pickup"
                label={t('lot.visibilityPickup')}
                hint={t('lot.visibilityPickupHelp')}
                checked={draft.showPickupArea}
                onChange={(event) => patch({ showPickupArea: event.target.checked })}
              />
              <CheckboxField
                id="lot-show-notes"
                label={t('lot.visibilityNotes')}
                hint={t('lot.visibilityNotesHelp')}
                checked={draft.showNotes}
                disabled={!draft.notes}
                onChange={(event) => patch({ showNotes: event.target.checked })}
              />

              <TextField
                id="lot-notes"
                label={t('lot.notes')}
                value={draft.notes}
                onChange={(event) => patch({ notes: event.target.value })}
              />

              <div className="inline-actions">
                <Button onClick={() => void onSave()} disabled={!canSubmit || saving}>
                  {saving ? t('lot.saving') : t('lot.save')}
                </Button>
                <Button variant="ghost" onClick={cancelForm}>
                  {t('common.cancel')}
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}

      <Card
        title={t('lot.title')}
        footer={
          isFarmer && !formOpen ? (
            <Button variant="secondary" onClick={startCreate}>
              {t('lot.new')}
            </Button>
          ) : undefined
        }
      >
        {loading && <LoadingState />}
        {loadError && <ErrorState onRetry={() => void loadLots()} />}

        {!loading && !loadError && lots.length === 0 && (
          <EmptyState title={t('lot.empty')} body={t('lot.emptyHelp')} />
        )}

        {lots.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t('lot.col.crop')}</th>
                  <th scope="col">{t('lot.col.quantity')}</th>
                  <th scope="col">{t('lot.col.ready')}</th>
                  <th scope="col">{t('lot.col.price')}</th>
                  <th scope="col">{t('lot.col.status')}</th>
                  <th scope="col">{t('lot.col.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {lots.map((lot) => {
                  const pause = PAUSE_FROM[lot.status]
                  const resume = RESUME_FROM[lot.status]
                  const editable = lot.status === 'draft' || lot.status === 'paused'
                  const commodityName =
                    lookupLocalized(commodities, lot.commodity_id, lot.commodity_name, locale) ??
                    `#${lot.commodity_id}`
                  const unitName = lookupLocalized(units, lot.unit_id, lot.unit_name, locale)

                  return (
                    <tr key={lot.id}>
                      <th scope="row">{commodityName}</th>
                      <td>
                        {lot.quantity} {unitName ?? ''}
                      </td>
                      <td>{lot.ready_date}</td>
                      <td>
                        {lot.expected_price_per_unit
                          ? lot.expected_price_per_unit
                          : t('lot.notStated')}
                      </td>
                      <td>
                        <Badge tone={STATUS_TONE[lot.status]}>
                          {t(STATUS_KEY[lot.status])}
                        </Badge>
                      </td>
                      <td>
                        <div className="inline-actions">
                          {lot.status === 'draft' && (
                            <Button
                              className="btn--sm"
                              variant="secondary"
                              disabled={busyId === lot.id}
                              onClick={() => void onMove(lot, 'published')}
                            >
                              {t('lot.publish')}
                            </Button>
                          )}
                          {pause && (
                            <Button
                              className="btn--sm"
                              variant="secondary"
                              disabled={busyId === lot.id}
                              onClick={() => void onMove(lot, pause)}
                            >
                              {t('lot.pause')}
                            </Button>
                          )}
                          {resume && (
                            <Button
                              className="btn--sm"
                              variant="secondary"
                              disabled={busyId === lot.id}
                              onClick={() => void onMove(lot, resume)}
                            >
                              {t('lot.resume')}
                            </Button>
                          )}
                          {editable && (
                            <Button
                              className="btn--sm"
                              variant="ghost"
                              onClick={() => startEdit(lot)}
                            >
                              {t('lot.edit')}
                            </Button>
                          )}
                          {lot.status !== 'archived' && (
                            <>
                              <Button
                                className="btn--sm"
                                variant="ghost"
                                disabled={busyId === lot.id}
                                onClick={() => void onMove(lot, 'closed')}
                              >
                                {t('lot.close')}
                              </Button>
                              <Button
                                className="btn--sm"
                                variant="ghost"
                                disabled={busyId === lot.id}
                                onClick={() => void onArchive(lot)}
                              >
                                {t('lot.archive')}
                              </Button>
                            </>
                          )}
                          <Button
                            className="btn--sm"
                            variant="ghost"
                            onClick={() => void showHistory(lot)}
                          >
                            {t('lot.historyTitle')}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {(counts.published ?? 0) > 0 && (
          <p className="muted">{t('lot.lockedNotice')}</p>
        )}
      </Card>

      {detail && (
        <Card
          title={`${t('lot.historyTitle')} - ${lookupLocalized(
            commodities,
            detail.commodity_id,
            detail.commodity_name,
            locale,
          )}`}
          footer={
            <Button variant="ghost" onClick={() => setDetail(null)}>
              {t('common.cancel')}
            </Button>
          }
        >
          {detail.history.length === 0 ? (
            <EmptyState title={t('lot.historyEmpty')} />
          ) : (
            <ul className="plain-list">
              {detail.history.map((entry) => (
                <li key={entry.id}>
                  {entry.from_status === null
                    ? t('lot.historyStarted')
                    : t('lot.historyEntry', {
                        from: t(STATUS_KEY[entry.from_status]),
                        to: t(STATUS_KEY[entry.to_status]),
                      })}
                  <span className="muted"> · {entry.changed_at.slice(0, 10)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  )
}