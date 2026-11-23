import { createContext, useContext } from 'react'

import type { LocaleCode, SessionUser, UserRole } from '../api/client'

export type AuthStep = 'phone' | 'otp' | 'role' | 'onboarding' | 'done'

export type AuthContextValue = {
  user: SessionUser | null
  step: AuthStep
  /** Present only in development with the mock SMS provider. */
  devCode: string | null
  maskedPhone: string | null
  phone: string
  begin: (phone: string, devCode: string | null, masked: string) => void
  completeVerification: (code: string) => Promise<void>
  chooseRole: (role: UserRole) => Promise<void>
  finishOnboarding: (name: string, locale: LocaleCode) => Promise<void>
  loginAsDemoRole: (role: UserRole, displayName?: string, phoneNum?: string) => Promise<void>
  signOut: () => Promise<void>
  reset: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

/** Access the auth session. Throws if used outside the provider. */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used inside <AuthProvider>')
  }
  return context
}