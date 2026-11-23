import { useContext } from 'react'

import { I18nContext, type I18nContextValue } from './context'

/** Access the translation function. Throws if used outside the provider. */
export function useTranslation(): I18nContextValue {
  const context = useContext(I18nContext)
  if (!context) {
    throw new Error('useTranslation must be used inside <I18nProvider>')
  }
  return context
}

export type { I18nContextValue, TranslationParams } from './context'