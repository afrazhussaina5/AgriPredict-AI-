import { useCallback, useMemo, useState, type ReactNode } from 'react'

import {
  completeOnboarding,
  fetchMe,
  logout as logoutRequest,
  requestOtp,
  selectRole as selectRoleRequest,
  setAccessToken,
  verifyOtp,
  type LocaleCode,
  type SessionUser,
  type UserRole,
} from '../api/client'
import { AuthContext, type AuthContextValue, type AuthStep } from './context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null)
  const [step, setStep] = useState<AuthStep>('phone')
  const [devCode, setDevCode] = useState<string | null>(null)
  const [maskedPhone, setMaskedPhone] = useState<string | null>(null)
  const [phone, setPhone] = useState('')

  const begin = useCallback(
    (nextPhone: string, code: string | null, masked: string) => {
      setPhone(nextPhone)
      setDevCode(code)
      setMaskedPhone(masked)
      // The code has been *requested*, not verified: show the OTP step next.
      // Jumping to 'role' here would call POST /auth/roles before a token
      // exists and fail with 401.
      setStep('otp')
    },
    [],
  )

  const completeVerification = useCallback(
    async (code: string) => {
      const result = await verifyOtp(phone, code)
      setAccessToken(result.access_token)
      setUser(result.user)
      // A user with no role yet must choose one before onboarding completes.
      setStep(result.user.roles.length === 0 ? 'role' : 'onboarding')
    },
    [phone],
  )

  const chooseRole = useCallback(async (role: UserRole) => {
    await selectRoleRequest(role)
    setUser(await fetchMe())
    setStep('onboarding')
  }, [])

  const finishOnboarding = useCallback(async (name: string, locale: LocaleCode) => {
    setUser(await completeOnboarding(name, locale))
    setStep('done')
  }, [])

  const loginAsDemoRole = useCallback(
    async (role: UserRole, displayName?: string, phoneNum?: string) => {
      const targetPhone =
        phoneNum ||
        (role === 'farmer'
          ? '+919876500001'
          : role === 'transport_provider'
            ? '+919876500002'
            : role === 'storage_provider'
              ? '+919876500003'
              : '+919876500004')
      const defaultName =
        displayName ||
        (role === 'farmer'
          ? 'Ramesh Patil (Farmer)'
          : role === 'transport_provider'
            ? 'Sunil Freight Logistics'
            : role === 'storage_provider'
              ? 'Sahyadri Agro Warehousing'
              : 'Kisan Mart Procurement')

      const otpRes = await requestOtp(targetPhone)
      const code = otpRes.dev_code || '123456'
      const verifyRes = await verifyOtp(targetPhone, code)
      setAccessToken(verifyRes.access_token)

      let currentUser = verifyRes.user
      if (currentUser.roles.length === 0 || !currentUser.roles.includes(role)) {
        await selectRoleRequest(role)
        currentUser = await fetchMe()
      }

      if (!currentUser.display_name) {
        currentUser = await completeOnboarding(defaultName, 'en')
      }

      setUser(currentUser)
      setStep('done')
    },
    [],
  )

  const signOut = useCallback(async () => {
    try {
      await logoutRequest()
    } finally {
      // Clear local state even if the network call failed.
      setAccessToken(null)
      setUser(null)
      setDevCode(null)
      setMaskedPhone(null)
      setPhone('')
      setStep('phone')
    }
  }, [])

  const reset = useCallback(() => {
    setDevCode(null)
    setMaskedPhone(null)
    setPhone('')
    setStep('phone')
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      step,
      devCode,
      maskedPhone,
      phone,
      begin,
      completeVerification,
      chooseRole,
      finishOnboarding,
      loginAsDemoRole,
      signOut,
      reset,
    }),
    [
      user,
      step,
      devCode,
      maskedPhone,
      phone,
      begin,
      completeVerification,
      chooseRole,
      finishOnboarding,
      loginAsDemoRole,
      signOut,
      reset,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}