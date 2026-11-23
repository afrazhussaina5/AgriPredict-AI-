export const APP_NAME = 'AgriPredict AI'

export const CURRENT_PHASE = 'Phase 6 — farmer lots, market prices and reference data'

export const SUPPORTED_LOCALES = ['en', 'hi', 'te'] as const

export type Locale = (typeof SUPPORTED_LOCALES)[number]

export function isSupportedLocale(value: string): value is Locale {
  return (SUPPORTED_LOCALES as readonly string[]).includes(value)
}
