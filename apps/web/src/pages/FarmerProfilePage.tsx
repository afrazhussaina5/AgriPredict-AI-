import { useCallback, useEffect, useState } from 'react'

import {
  ApiError,
  fetchFarmerProfile,
  updateFarmerProfile,
  type FarmerProfile,
} from '../api/client'
import { useAuth } from '../auth/context'
import { CheckboxField, SelectField, TextField } from '../components/fields'
import { EmptyState, ErrorState, LoadingState } from '../components/states'
import { Alert, Button, Card } from '../components/ui'
import { displayReferenceName, useLocationCascade } from '../components/useLocationCascade'
import { useTranslation } from '../i18n/useTranslation'
import { useLocationContext } from '../context/LocationContext'

/* The farmer's own profile.

   Built from the existing design system only - Card, .stack, .field and
   CheckboxField. No page-specific CSS.

   The two privacy switches carry the same defaults as the lot form: exact
   location and phone sharing are OFF unless the farmer turns them on. */

export function FarmerProfilePage() {
  const { t, locale } = useTranslation()
  const { user } = useAuth()
  const { activeHub } = useLocationContext()

  const [profile, setProfile] = useState<FarmerProfile | null>(null)
  const [noProfileYet, setNoProfileYet] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)

  const [fullName, setFullName] = useState('')
  const [village, setVillage] = useState('')
  const [bio, setBio] = useState('')
  const [showLocation, setShowLocation] = useState(false)
  const [showPhone, setShowPhone] = useState(false)

  const location = useLocationCascade()

  const signedIn = user !== null
  const isFarmer = user?.roles.includes('farmer') ?? false

  const load = useCallback(async () => {
    if (!signedIn) {
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const next = await fetchFarmerProfile()
      setProfile(next)
      setFullName(next.full_name)
      setVillage(next.village_or_town ?? '')
      setBio(next.bio ?? '')
      setShowLocation(next.show_exact_location_to_buyers)
      setShowPhone(next.contact_phone_visible)
      setLoadError(false)
      setNoProfileYet(false)
    } catch (error) {
      // A 404 is the normal first-run state, not a failure: Phase 4 onboarding
      // creates the account but not the farmer profile.
      if (error instanceof ApiError && error.status === 404) {
        setNoProfileYet(true)
        setLoadError(false)
      } else {
        setLoadError(true)
      }
    } finally {
      setLoading(false)
    }
  }, [signedIn])

  useEffect(() => {
    void load()
  }, [load])

  async function onSave() {
    if (!isFarmer) return
    setSaving(true)
    setSaveError(null)
    setSaved(false)
    try {
      const next = await updateFarmerProfile({
        full_name: fullName,
        village_or_town: village,
        bio,
        state_id: location.stateId,
        district_id: location.districtId,
        mandi_id: location.mandiId,
        show_exact_location_to_buyers: showLocation,
        contact_phone_visible: showPhone,
      })
      setProfile(next)
      setSaved(true)
    } catch (error) {
      setSaveError(error instanceof ApiError ? error.message : t('state.error.body'))
    } finally {
      setSaving(false)
    }
  }

  if (!signedIn) {
    return (
      <div className="stack">
        <div>
          <h1>{t('farmer.title')}</h1>
          <p className="lede">{t('farmer.subtitle')}</p>
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

  return (
    <div className="stack anim-fade-in">
      <div>
        <h1>{t('farmer.title')}</h1>
        <p className="lede">{t('farmer.subtitle')}</p>
      </div>

      {loading && <LoadingState />}
      {loadError && <ErrorState onRetry={() => void load()} />}

      {noProfileYet && !loadError && (
        <Alert tone="info" title={t('farmer.notFound')}>
          <p>{t('farmer.subtitle')}</p>
        </Alert>
      )}

      {saved && (
        <Alert tone="success">
          <p>{t('farmer.saved')}</p>
        </Alert>
      )}
      {saveError && (
        <Alert tone="error" title={t('state.error.title')}>
          <p>{saveError}</p>
        </Alert>
      )}

      {!loading && !loadError && (profile || noProfileYet) && (
        <Card
          title={
            profile
              ? t('farmer.completion', { percent: profile.completion_percent })
              : t('farmer.title')
          }
        >
          <div className="stack">
            <h3>{t('farmer.section.about')}</h3>
            <TextField
              id="profile-full-name"
              label={t('farmer.fullName')}
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
            />
            <TextField
              id="profile-village"
              label={t('farmer.village')}
              value={village}
              onChange={(event) => setVillage(event.target.value)}
            />
            <TextField
              id="profile-bio"
              label={t('farmer.bio')}
              value={bio}
              onChange={(event) => setBio(event.target.value)}
            />

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0 }}>{t('farmer.section.location')}</h3>
              <span className="text-caption muted">
                📍 Default Hub: <strong>{activeHub.district}, {activeHub.state}</strong>
              </span>
            </div>
            <SelectField
              id="profile-state"
              label={t('ref.state.label')}
              value={location.stateId ?? profile?.state_id ?? ''}
              onChange={(event) =>
                location.setStateId(event.target.value ? Number(event.target.value) : null)
              }
            >
              <option value="">{t('farmer.notSet')}</option>
              {(location.states.status === 'ready' ? location.states.data : []).map((row) => (
                <option key={row.id} value={row.id}>
                  {displayReferenceName(row, locale)}
                </option>
              ))}
            </SelectField>

            {location.stateId !== null && location.districts.status === 'ready' && (
              <SelectField
                id="profile-district"
                label={t('ref.district.label')}
                value={location.districtId ?? profile?.district_id ?? ''}
                onChange={(event) =>
                  location.setDistrictId(
                    event.target.value ? Number(event.target.value) : null,
                  )
                }
              >
                <option value="">{t('farmer.notSet')}</option>
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
                id="profile-mandi"
                label={t('ref.mandi.label')}
                value={location.mandiId ?? ''}
                onChange={(event) =>
                  location.setMandiId(event.target.value ? Number(event.target.value) : null)
                }
              >
                <option value="">{t('farmer.notSet')}</option>
                {(location.mandis.status === 'ready' ? location.mandis.data : []).map((row) => (
                  <option key={row.id} value={row.id}>
                    {displayReferenceName(row, locale)}
                  </option>
                ))}
              </SelectField>
            )}

            <h3>{t('farmer.section.privacy')}</h3>
            <CheckboxField
              id="profile-show-location"
              label={t('farmer.showExactLocation')}
              hint={t('farmer.showExactLocationHelp')}
              checked={showLocation}
              onChange={(event) => setShowLocation(event.target.checked)}
            />
            <CheckboxField
              id="profile-show-phone"
              label={t('farmer.showPhone')}
              hint={t('farmer.showPhoneHelp')}
              checked={showPhone}
              onChange={(event) => setShowPhone(event.target.checked)}
            />

            <div className="inline-actions">
              <Button onClick={() => void onSave()} disabled={saving || !isFarmer}>
                {saving ? t('farmer.saving') : t('common.save')}
              </Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}