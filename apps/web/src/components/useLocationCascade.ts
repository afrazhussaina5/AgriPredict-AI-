import { useCallback, useEffect, useState } from 'react'

import {
  fetchDistricts,
  fetchMandis,
  fetchStates,
  type District,
  type Mandi,
  type State,
} from '../api/client'

/* State -> District -> Mandi cascade shared by the farmer profile and the lot
   form.

   Kept in its own module (not exported from a page) because a file that exports
   both a component and a hook trips the react-refresh lint rule.

   Selecting a parent always clears its children, so the form can never submit a
   district that belongs to a different state. */

export type Loadable<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; data: T }
  | { status: 'error' }

const IDLE: Loadable<never> = { status: 'idle' }
const LOADING: Loadable<never> = { status: 'loading' }

export type LocationCascade = {
  states: Loadable<State[]>
  districts: Loadable<District[]>
  mandis: Loadable<Mandi[]>
  stateId: number | null
  districtId: number | null
  mandiId: number | null
  setStateId: (next: number | null) => void
  setDistrictId: (next: number | null) => void
  setMandiId: (next: number | null) => void
  reloadStates: () => void
}

/** Show the localized name when a verified translation exists, else the original. */
export function displayReferenceName(
  row: { name: string; name_hi: string | null; name_te: string | null },
  locale: string,
): string {
  if (locale === 'hi' && row.name_hi) return row.name_hi
  if (locale === 'te' && row.name_te) return row.name_te
  return row.name
}

export function useLocationCascade(initialStateId?: number | null): LocationCascade {
  const [states, setStates] = useState<Loadable<State[]>>(LOADING)
  const [districts, setDistricts] = useState<Loadable<District[]>>(IDLE)
  const [mandis, setMandis] = useState<Loadable<Mandi[]>>(IDLE)

  const [stateId, setStateId] = useState<number | null>(initialStateId ?? null)
  const [districtId, setDistrictId] = useState<number | null>(null)
  const [mandiId, setMandiId] = useState<number | null>(null)

  const loadStates = useCallback(async () => {
    setStates(LOADING)
    try {
      setStates({ status: 'ready', data: await fetchStates() })
    } catch {
      setStates({ status: 'error' })
    }
  }, [])

  useEffect(() => {
    void loadStates()
  }, [loadStates])

  // Seed the cascade from an existing profile so the farmer does not have to
  // re-pick a location they already chose. Runs once per distinct initial value.
  useEffect(() => {
    if (initialStateId) void selectState(initialStateId)
  }, [initialStateId])

  async function selectState(next: number | null) {
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

  async function selectDistrict(next: number | null) {
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

  function selectMandi(next: number | null) {
    setMandiId(next)
  }

  return {
    states,
    districts,
    mandis,
    stateId,
    districtId,
    mandiId,
    setStateId: (next) => void selectState(next),
    setDistrictId: (next) => void selectDistrict(next),
    setMandiId: selectMandi,
    reloadStates: () => void loadStates(),
  }
}