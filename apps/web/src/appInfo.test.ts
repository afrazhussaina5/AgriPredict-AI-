import { describe, expect, it } from 'vitest'

import { APP_NAME, SUPPORTED_LOCALES, isSupportedLocale } from './appInfo'

describe('appInfo', () => {
  it('exposes the product name', () => {
    expect(APP_NAME).toBe('AgriPredict AI')
  })

  it('declares English, Hindi and Telugu support', () => {
    expect([...SUPPORTED_LOCALES]).toEqual(['en', 'hi', 'te'])
  })

  it('validates locale codes', () => {
    expect(isSupportedLocale('te')).toBe(true)
    expect(isSupportedLocale('fr')).toBe(false)
  })
})
