import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { SUPPORTED_LOCALES, type Locale } from '../appInfo'
import { formatTranslation, translations, type TranslationKey } from './translations'
import { I18nContext, type I18nContextValue, type TranslationParams } from './context'

const STORAGE_KEY = 'agripredict.locale'

function isLocale(value: string | null): value is Locale {
  return value !== null && (SUPPORTED_LOCALES as readonly string[]).includes(value)
}

/** Read the persisted preference. Returns null when nothing valid is stored. */
function readStoredLocale(): Locale | null {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return isLocale(stored) ? stored : null
  } catch {
    // Storage can be unavailable (private mode, blocked cookies).
    return null
  }
}

/** Fall back to the browser language, then to English. */
function detectInitialLocale(): Locale {
  const stored = readStoredLocale()
  if (stored) return stored

  try {
    const candidates = navigator.languages ?? [navigator.language]
    for (const candidate of candidates) {
      const base = candidate.toLowerCase()
      if (base.startsWith('te')) return 'te'
      if (base.startsWith('hi')) return 'hi'
      if (base.startsWith('en')) return 'en'
    }
  } catch {
    // navigator may be unavailable in exotic environments.
  }
  return 'en'
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(detectInitialLocale)

  // Persist the choice and keep the document language correct for screen
  // readers and browser translation behaviour.
  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, locale)
    } catch {
      // Preference simply will not persist; the app still works.
    }
    document.documentElement.lang = locale
  }, [locale])

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next)
  }, [])

  const t = useCallback(
    (key: TranslationKey, params?: TranslationParams) => {
      const table = translations[locale] ?? translations.en
      const template = table[key] ?? translations.en[key] ?? key
      return formatTranslation(template, params)
    },
    [locale],
  )

  const value = useMemo<I18nContextValue>(
    () => ({ locale, setLocale, t }),
    [locale, setLocale, t],
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}