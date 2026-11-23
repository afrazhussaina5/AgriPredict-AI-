import type { ButtonHTMLAttributes, ReactNode } from 'react'

/* Presentational building blocks.
   These components contain NO translated text on purpose: callers pass
   translated strings, so every visible word stays in the translation files. */

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'gold'

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
}

export function Button({ variant = 'primary', className = '', type = 'button', ...rest }: ButtonProps) {
  return <button type={type} className={`btn btn--${variant} ${className}`.trim()} {...rest} />
}

export function Card({
  title,
  accent,
  badge,
  children,
  footer,
}: {
  title?: ReactNode
  accent?: boolean
  badge?: ReactNode
  children?: ReactNode
  footer?: ReactNode
}) {
  return (
    <section className={`card${accent ? ' card--accent' : ''}`}>
      {(title || badge) && (
        <div className="card__header">
          {title && <h3 className="card__title">{title}</h3>}
          {badge}
        </div>
      )}
      {children}
      {footer && <div className="card__footer">{footer}</div>}
    </section>
  )
}

export function Badge({
  tone = 'neutral',
  className = '',
  children,
}: {
  tone?: 'neutral' | 'success' | 'warning' | 'error' | 'info' | 'gold'
  className?: string
  children: ReactNode
}) {
  return <span className={`badge badge--${tone} ${className}`.trim()}>{children}</span>
}

export function Alert({
  tone = 'info',
  title,
  children,
}: {
  tone?: 'info' | 'success' | 'warning' | 'error'
  title?: ReactNode
  children?: ReactNode
}) {
  return (
    <div className={`alert alert--${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <div className="alert__body">
        {title && <p className="alert__title">{title}</p>}
        {children}
      </div>
    </div>
  )
}

export function Spinner() {
  return <span className="spinner" aria-hidden="true" />
}
