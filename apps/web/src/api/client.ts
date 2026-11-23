/* Typed API client.
   Errors are surfaced as ApiError with the backend's safe message; the token is
   kept in memory only and is never written to localStorage (an XSS bug must not
   be able to steal a long-lived session). */

export type ApiErrorPayload = {
  error?: { code?: string; message?: string; details?: unknown }
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

let accessToken: string | null = null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getAccessToken(): string | null {
  return accessToken
}

const BASE = '/api/v1'

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body) headers.set('Content-Type', 'application/json')
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)

  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, { ...init, headers })
  } catch {
    // Network failure: the backend is not reachable. Never guess a status.
    throw new ApiError(0, 'network_error', 'Cannot reach the server.')
  }

  if (response.status === 204) return undefined as T

  const text = await response.text()
  let payload: unknown = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = null
    }
  }

  if (!response.ok) {
    const error = (payload as ApiErrorPayload)?.error
    throw new ApiError(
      response.status,
      error?.code ?? 'unknown_error',
      error?.message ?? 'The request could not be completed.',
    )
  }
  return payload as T
}

/* ------------------------------------------------------------------- types */

export type LocaleCode = 'en' | 'hi' | 'te'
export type UserRole = 'farmer' | 'buyer' | 'transport_provider' | 'storage_provider' | 'admin'

export type SessionUser = {
  id: number
  display_name: string | null
  phone_masked: string | null
  status: string
  preferred_locale: LocaleCode
  roles: UserRole[]
  phone_verified: boolean
  onboarding_complete: boolean
}

export type OtpRequestResponse = {
  message: string
  phone_masked: string
  expires_in_seconds: number
  resend_after_seconds: number
  /** Present only in development with the mock provider. */
  dev_code: string | null
}

export type TokenResponse = {
  access_token: string
  token_type: string
  expires_at: string
  user: SessionUser
}

/* -------------------------------------------------------------------- calls */

export function requestOtp(phone: string, role?: UserRole): Promise<OtpRequestResponse> {
  return request<OtpRequestResponse>('/auth/otp/request', {
    method: 'POST',
    body: JSON.stringify({ phone, role }),
  })
}

export function verifyOtp(phone: string, code: string): Promise<TokenResponse> {
  return request<TokenResponse>('/auth/otp/verify', {
    method: 'POST',
    body: JSON.stringify({ phone, code }),
  })
}

export function fetchMe(): Promise<SessionUser> {
  return request<SessionUser>('/auth/me')
}

export function selectRole(role: UserRole): Promise<{ message: string }> {
  return request<{ message: string }>('/auth/roles', {
    method: 'POST',
    body: JSON.stringify({ role }),
  })
}

export function completeOnboarding(
  displayName: string,
  preferredLocale: LocaleCode,
): Promise<SessionUser> {
  return request<SessionUser>('/auth/onboarding', {
    method: 'POST',
    body: JSON.stringify({ display_name: displayName, preferred_locale: preferredLocale }),
  })
}

export function logout(): Promise<{ message: string }> {
  return request<{ message: string }>('/auth/logout', { method: 'POST' })
}
/* ------------------------------------------------------- reference data */

/** Provenance travels with every reference row so the UI can show it. */
export type ReferenceProvenance = {
  source_key: string
  source_name: string
  source_is_official: boolean
}

export type State = ReferenceProvenance & {
  id: number
  code: string
  name: string
  name_hi: string | null
  name_te: string | null
}

export type District = ReferenceProvenance & {
  id: number
  code: string
  name: string
  name_hi: string | null
  name_te: string | null
  state_id: number
}

export type Mandi = ReferenceProvenance & {
  id: number
  code: string
  name: string
  name_hi: string | null
  name_te: string | null
  district_id: number
  state_id: number
  has_storage: boolean | null
}

export type Locality = ReferenceProvenance & {
  id: number
  name: string
  name_hi: string | null
  name_te: string | null
  district_id: number
  kind: 'city' | 'town' | 'village'
  latitude: number | null
  longitude: number | null
}

export type Commodity = ReferenceProvenance & {
  id: number
  code: string
  name: string
  name_hi: string | null
  name_te: string | null
  category: string | null
}

export type Variety = ReferenceProvenance & {
  id: number
  code: string
  name: string
  name_hi: string | null
  name_te: string | null
  commodity_id: number
}

export type ReferenceStatus = {
  is_populated: boolean
  counts: Record<string, number>
  sources: Array<{ id: number; source_key: string; name: string; is_official: boolean }>
  oldest_import_at: string | null
  newest_import_at: string | null
  note: string
}

export function fetchReferenceStatus(): Promise<ReferenceStatus> {
  return request<ReferenceStatus>('/reference/status')
}

export function fetchStates(): Promise<State[]> {
  return request<State[]>('/reference/states')
}

export function fetchDistricts(stateId: number): Promise<District[]> {
  return request<District[]>(`/reference/states/${stateId}/districts`)
}

export function fetchLocalities(districtId: number): Promise<Locality[]> {
  return request<Locality[]>(`/reference/districts/${districtId}/localities`)
}

export function fetchMandis(districtId?: number): Promise<Mandi[]> {
  const query = districtId ? `?district_id=${districtId}` : ''
  return request<Mandi[]>(`/reference/mandis${query}`)
}

export function fetchCommodities(): Promise<Commodity[]> {
  return request<Commodity[]>('/reference/commodities')
}

export function fetchVarieties(commodityId: number): Promise<Variety[]> {
  return request<Variety[]>(`/reference/commodities/${commodityId}/varieties`)
}

export type Grade = ReferenceProvenance & {
  id: number
  code: string
  name: string
  name_hi: string | null
  name_te: string | null
  /** Null means the grade applies to every commodity. */
  commodity_id: number | null
}

export function fetchGrades(commodityId?: number): Promise<Grade[]> {
  const query = commodityId ? `?commodity_id=${commodityId}` : ''
  return request<Grade[]>(`/reference/grades${query}`)
}

export type Unit = ReferenceProvenance & {
  id: number
  code: string
  name: string
  name_hi: string | null
  name_te: string | null
  /** Mass, volume, count or bag. Blocks comparing kg with litres. */
  dimension: 'mass' | 'volume' | 'count' | 'bag'
  /** Kilograms represented by one unit. Null for non-mass units. */
  to_base_kg: number | null
}

export function fetchUnits(): Promise<Unit[]> {
  return request<Unit[]>('/reference/units')
}

/* ------------------------------------------------- farmer profile & lots */

/** The full lifecycle. Mirrors the server's ALLOWED_LOT_TRANSITIONS. */
export type LotStatus = 'draft' | 'published' | 'paused' | 'closed' | 'archived'

export type FarmerProfile = {
  id: number
  full_name: string
  organisation_name: string | null
  preferred_language: LocaleCode
  state_id: number | null
  district_id: number | null
  mandi_id: number | null
  village_or_town: string | null
  bio: string | null
  show_exact_location_to_buyers: boolean
  contact_phone_visible: boolean
  completion_percent: number
  status: string
  state_name: string | null
  district_name: string | null
  mandi_name: string | null
}

export type FarmerProfileUpdate = {
  full_name?: string
  organisation_name?: string
  village_or_town?: string
  bio?: string
  state_id?: number | null
  district_id?: number | null
  mandi_id?: number | null
  show_exact_location_to_buyers?: boolean
  contact_phone_visible?: boolean
}

/** The owner's view: every field, hidden or not. */
export type Lot = {
  id: number
  farmer_id: number
  commodity_id: number
  variety_id: number | null
  grade_id: number | null
  /** Strings, not numbers: Decimal money must never pass through a JS float. */
  quantity: string
  unit_id: number
  pickup_district_id: number | null
  pickup_mandi_id: number | null
  pickup_area_label: string | null
  ready_date: string
  expected_price_per_unit: string | null
  min_expected_price_per_unit: string | null
  show_expected_price: boolean
  show_pickup_area: boolean
  show_notes: boolean
  notes: string | null
  status: LotStatus
  published_at: string | null
  closed_at: string | null
  archived_at: string | null
  closed_reason: string | null
  commodity_name: string | null
  variety_name: string | null
  grade_name: string | null
  unit_name: string | null
  unit_code: string | null
  pickup_district_name: string | null
  pickup_mandi_name: string | null
}

export type LotHistoryEntry = {
  id: number
  from_status: LotStatus | null
  to_status: LotStatus
  note: string | null
  changed_at: string
}

export type LotDetail = Lot & {
  history: LotHistoryEntry[]
  allowed_transitions: LotStatus[]
}

export type LotList = {
  items: Lot[]
  total: number
  limit: number
  offset: number
}

/** What the farmer sends when creating or editing a lot. */
export type LotInput = {
  commodity_id: number
  variety_id?: number | null
  grade_id?: number | null
  quantity: string
  unit_id: number
  ready_date: string
  pickup_district_id?: number | null
  pickup_mandi_id?: number | null
  pickup_area_label?: string | null
  expected_price_per_unit?: string | null
  min_expected_price_per_unit?: string | null
  notes?: string | null
  show_expected_price?: boolean
  show_pickup_area?: boolean
  show_notes?: boolean
}

export function fetchFarmerProfile(): Promise<FarmerProfile> {
  return request<FarmerProfile>('/farmer/profile')
}

export function updateFarmerProfile(
  payload: FarmerProfileUpdate,
): Promise<FarmerProfile> {
  return request<FarmerProfile>('/farmer/profile', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function fetchMyLots(params?: {
  status?: LotStatus
  limit?: number
  offset?: number
}): Promise<LotList> {
  const query = new URLSearchParams()
  if (params?.status) query.set('status', params.status)
  if (params?.limit) query.set('limit', String(params.limit))
  if (params?.offset) query.set('offset', String(params.offset))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return request<LotList>(`/lots${suffix}`)
}

export function fetchLot(lotId: number): Promise<LotDetail> {
  return request<LotDetail>(`/lots/${lotId}`)
}

export function createLot(payload: LotInput): Promise<Lot> {
  return request<Lot>('/lots', { method: 'POST', body: JSON.stringify(payload) })
}

export function updateLot(lotId: number, payload: Partial<LotInput>): Promise<Lot> {
  return request<Lot>(`/lots/${lotId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

/** Ask the server to move a lot's status. The server decides if it is legal. */
export function changeLotStatus(
  lotId: number,
  status: LotStatus,
  reason?: string,
): Promise<LotDetail> {
  return request<LotDetail>(`/lots/${lotId}/status`, {
    method: 'POST',
    body: JSON.stringify(reason ? { status, reason } : { status }),
  })
}

export function archiveLot(lotId: number): Promise<{ message: string }> {
  return request<{ message: string }>(`/lots/${lotId}`, { method: 'DELETE' })
}

/* --------------------------------------------------- public market board */

/** One row of the public mandi price board (Phase 6).
 *  `modal_price` is a decimal string or null - never a float, and null means
 *  the source shipped no price (the board renders it as blank, not 0). */
export type MarketPriceRow = {
  commodity_code: string
  commodity_name: string
  /** A, B, C, or UNKNOWN when the source row carried no grade. */
  grade: string
  mandi_name: string
  mandi_code: string
  district_name: string
  state_name: string
  market_date: string
  modal_price: string | null
  unit_code: string
  arrivals: number | null
  source_name: string
  imported_at: string
}

export type MarketCommodity = { code: string; name: string; category: string | null }

/** A grade that actually appears on the board, with the id the price query
 *  filters on. Grades with no imported row are omitted by the server. */
export type MarketGrade = {
  id: number
  code: string
  name: string
  commodity_id: number | null
  commodity_code: string | null
  row_count: number
}

export function fetchMarketPrices(params?: {
  commodity_id?: number
  grade_id?: number
  district_id?: number
}): Promise<MarketPriceRow[]> {
  const query = new URLSearchParams()
  if (params?.commodity_id !== undefined) query.set('commodity_id', String(params.commodity_id))
  if (params?.grade_id !== undefined) query.set('grade_id', String(params.grade_id))
  if (params?.district_id !== undefined) query.set('district_id', String(params.district_id))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return request<MarketPriceRow[]>(`/market/prices${suffix}`)
}

export function fetchMarketCommodities(): Promise<MarketCommodity[]> {
  return request<MarketCommodity[]>('/market/commodities')
}

export function fetchMarketGrades(): Promise<MarketGrade[]> {
  return request<MarketGrade[]>('/market/grades')
}

/** When the pipeline last touched upstream - not the latest market day. */
export function fetchMarketFreshness(): Promise<{ last_imported_at: string | null }> {
  return request<{ last_imported_at: string | null }>('/market/freshness')
}

/* --------------------------------------------------- weather & ml forecast */

export type AgriculturalWeather = {
  location: string
  district: string
  state: string
  temp_c: number
  feels_like_c: number
  humidity_pct: number
  precipitation_chance_pct: number
  wind_kph: number
  condition: string
  harvest_status: 'ideal' | 'caution' | 'moderate'
  harvest_label: string
  advisory: { en: string; hi: string; te: string }
  daily_forecast: Array<{
    date: string
    day: string
    temp_c: number
    rain_prob_pct: number
    condition: string
  }>
  observation_time: string
}

export function fetchAgriculturalWeather(
  district = 'Nashik',
  state = 'Maharashtra',
): Promise<AgriculturalWeather> {
  const query = new URLSearchParams({ district, state })
  return request<AgriculturalWeather>(`/market/weather?${query.toString()}`)
}

export type ForecastPoint = {
  date: string
  day_label: string
  price: number
  lower_bound: number
  upper_bound: number
  is_historical: boolean
  confidence_pct: number
}

export type SeriesForecastResponse = {
  commodity: string
  grade: string
  state: string
  district: string
  market: string
  base_benchmark_price: number
  projected_price_horizon: number
  price_change_projected_pct: number
  expected_gain_per_qtl: number
  unit: string
  horizon_days: number
  action: 'STORE' | 'SELL_NOW' | 'WATCH'
  action_title: string
  action_summary: string
  action_color: string
  recommendation: 'HOLD' | 'SELL_SOON' | 'NEUTRAL'
  rationale: string
  is_perishable: boolean
  points: ForecastPoint[]
  model_version: string
  methodology: string
  disclaimer: string
}

export function fetchForecastSeries(params: {
  commodity: string
  grade?: string
  state: string
  district: string
  market: string
  days?: number
}): Promise<SeriesForecastResponse> {
  const query = new URLSearchParams({
    commodity: params.commodity,
    grade: params.grade || 'FAQ',
    state: params.state,
    district: params.district,
    market: params.market,
    days: String(params.days || 10),
  })
  return request<SeriesForecastResponse>(`/market/forecast/series?${query.toString()}`)
}

