import { createContext } from 'react'

import type { Locale } from '../appInfo'
import type { TranslationKey } from './translations'

export type TranslationParams = Record<string, string | number>

export type I18nContextValue = {
  locale: Locale
  setLocale: (next: Locale) => void
  t: (key: TranslationKey, params?: TranslationParams) => string
}

/* Kept in its own module so the provider file exports only a component,
   which is what React Fast Refresh requires for correct hot reloading. */
export const I18nContext = createContext<I18nContextValue | null>(null)