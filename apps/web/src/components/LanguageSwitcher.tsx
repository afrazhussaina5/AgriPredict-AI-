import { SUPPORTED_LOCALES, type Locale } from '../appInfo'
import { useTranslation } from '../i18n/useTranslation'

const LOCALE_NATIVE_NAME: Record<Locale, string> = {
  en: 'English',
  hi: 'हिन्दी',
  te: 'తెలుగు',
}

export function LanguageSwitcher() {
  const { locale, setLocale, t } = useTranslation()
  const controlId = 'language-select'

  return (
    <div className="lang-switch">
      <label className="lang-switch__label" htmlFor={controlId}>
        {t('common.languageLabel')}
      </label>
      <select
        id={controlId}
        className="lang-switch__select"
        value={locale}
        onChange={(event) => setLocale(event.target.value as Locale)}
      >
        {SUPPORTED_LOCALES.map((code) => (
          <option key={code} value={code}>
            {LOCALE_NATIVE_NAME[code]}
          </option>
        ))}
      </select>
    </div>
  )
}
