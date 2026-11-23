import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react'

/* Accessible form primitives: label + hint + control + error, wired together
   with aria-describedby / aria-invalid. Used by every form from Phase 4 on. */

type FieldShellProps = {
  label: ReactNode
  controlId: string
  hint?: string
  error?: string
  children: ReactNode
}

function FieldShell({ label, controlId, hint, error, children }: FieldShellProps) {
  return (
    <div className={`field${error ? ' field--invalid' : ''}`}>
      <label className="field__label" htmlFor={controlId}>
        {label}
      </label>
      {hint && (
        <span className="field__hint" id={`${controlId}-hint`}>
          {hint}
        </span>
      )}
      {children}
      {error && (
        <span className="field__error" id={`${controlId}-error`} role="alert">
          {error}
        </span>
      )}
    </div>
  )
}

function describedBy(controlId: string, hint?: string, error?: string): string | undefined {
  const ids = [hint ? `${controlId}-hint` : '', error ? `${controlId}-error` : ''].filter(Boolean)
  return ids.length > 0 ? ids.join(' ') : undefined
}

export type TextFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> & {
  id: string
  label: ReactNode
  hint?: string
  error?: string
}

export function TextField({ id, label, hint, error, ...inputProps }: TextFieldProps) {
  return (
    <FieldShell label={label} controlId={id} hint={hint} error={error}>
      <input
        id={id}
        className="field__control"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
        autoComplete={inputProps.autoComplete}
        maxLength={inputProps.maxLength}
        inputMode={inputProps.inputMode}
        pattern={inputProps.pattern}
        {...inputProps}
      />
    </FieldShell>
  )
}

export type SelectFieldProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id'> & {
  id: string
  label: ReactNode
  hint?: string
  error?: string
  children: ReactNode
}

export function SelectField({ id, label, hint, error, children, ...selectProps }: SelectFieldProps) {
  return (
    <FieldShell label={label} controlId={id} hint={hint} error={error}>
      <select
        id={id}
        className="field__control"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
        {...selectProps}
      >
        {children}
      </select>
    </FieldShell>
  )
}

export type CheckboxFieldProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  'id' | 'type' | 'className'
> & {
  id: string
  label: ReactNode
  hint?: string
  error?: string
}

/**
 * A labelled checkbox with the same hint/error wiring as every other field.
 *
 * Added in Phase 6, the first phase to use opt-in toggles (which fields of a
 * lot a buyer may see). It reuses `.field__hint` and `.field__error` so the
 * typography matches the rest of the form instead of inventing a parallel look.
 *
 * The control and label sit on one row, with hint and error wrapping onto a
 * second column beneath, so a group of toggles stays scannable.
 */
export function CheckboxField({ id, label, hint, error, ...inputProps }: CheckboxFieldProps) {
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  const described = [hintId, errorId].filter(Boolean).join(' ') || undefined

  return (
    <div className={`checkbox-field${error ? ' field--invalid' : ''}`}>
      <input
        id={id}
        type="checkbox"
        className="checkbox-field__control"
        aria-invalid={error ? true : undefined}
        aria-describedby={described}
        {...inputProps}
      />
      <label className="checkbox-field__label" htmlFor={id}>
        {label}
      </label>
      {hint && (
        <span className="field__hint checkbox-field__meta" id={hintId}>
          {hint}
        </span>
      )}
      {error && (
        <span className="field__error checkbox-field__meta" id={errorId} role="alert">
          {error}
        </span>
      )}
    </div>
  )
}
