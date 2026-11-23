import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

export type ToastTone = 'success' | 'info' | 'warning'

export type ToastMessage = {
  id: string
  text: string
  tone?: ToastTone
}

type ToastContextType = {
  showToast: (text: string, tone?: ToastTone) => void
}

const ToastContext = createContext<ToastContextType | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([])

  const showToast = useCallback((text: string, tone: ToastTone = 'success') => {
    const id = `${Date.now()}-${Math.random().toString(36).substring(2, 7)}`
    setToasts((prev) => [...prev, { id, text, tone }])

    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 4000)
  }, [])

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {toasts.length > 0 && (
        <div className="toast-container" role="status" aria-live="polite">
          {toasts.map((toast) => (
            <div key={toast.id} className={`toast toast--${toast.tone ?? 'success'}`}>
              <span>{toast.tone === 'warning' ? '⚠️' : toast.tone === 'info' ? 'ℹ️' : '✓'}</span>
              <span>{toast.text}</span>
            </div>
          ))}
        </div>
      )}
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    return {
      showToast: (text: string) => {
        // Fallback if rendered outside provider
        console.info('[Toast]', text)
      },
    }
  }
  return ctx
}
