import { describe, expect, it } from 'vitest'

import { SUPPORTED_LOCALES } from '../appInfo'
import { TRANSLATION_KEYS, formatTranslation, translations } from './translations'

describe('translation resources', () => {
  it('defines exactly the supported locales', () => {
    expect(Object.keys(translations).sort()).toEqual([...SUPPORTED_LOCALES].sort())
  })

  it('has identical key sets across English, Hindi and Telugu', () => {
    const reference = [...TRANSLATION_KEYS].sort()
    for (const locale of SUPPORTED_LOCALES) {
      const keys = Object.keys(translations[locale]).sort()
      expect(keys, `locale "${locale}" must match the English key set`).toEqual(reference)
    }
  })

  it('contains no empty or whitespace-only strings', () => {
    for (const locale of SUPPORTED_LOCALES) {
      for (const key of TRANSLATION_KEYS) {
        expect(translations[locale][key].trim(), `${locale}:${key}`).not.toBe('')
      }
    }
  })

  it('keeps the same {placeholders} in every locale', () => {
    const placeholders = (text: string): string[] => (text.match(/\{\w+\}/g) ?? []).sort()
    for (const key of TRANSLATION_KEYS) {
      const expected = placeholders(translations.en[key])
      for (const locale of SUPPORTED_LOCALES) {
        expect(placeholders(translations[locale][key]), `${locale}:${key}`).toEqual(expected)
      }
    }
  })

  it('never claims live data in the footer notice', () => {
    for (const locale of SUPPORTED_LOCALES) {
      expect(translations[locale]['common.footerText']).toBeTruthy()
    }
  })
})

describe('formatTranslation', () => {
  it('substitutes named parameters', () => {
    expect(formatTranslation('version {version} on {environment}', {
      version: '1.0.0',
      environment: 'development',
    })).toBe('version 1.0.0 on development')
  })

  it('keeps unknown placeholders untouched', () => {
    expect(formatTranslation('keep {missing} as-is', { other: 'x' })).toBe('keep {missing} as-is')
  })

  it('returns the template unchanged without parameters', () => {
    expect(formatTranslation('plain text')).toBe('plain text')
  })
})
