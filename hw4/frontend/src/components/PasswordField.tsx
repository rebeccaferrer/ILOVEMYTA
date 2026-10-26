import { useId, useState, type InputHTMLAttributes } from 'react'

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & {
  label: string
  hint?: string
  errors?: string[]
}

/** Password input with a Show/Hide button, an optional hint and error list. */
export default function PasswordField({ label, hint, errors = [], ...input }: Props) {
  const [visible, setVisible] = useState(false)
  const id = useId()
  const describedBy = [hint && `${id}-hint`, errors.length > 0 && `${id}-errors`].filter(Boolean).join(' ') || undefined

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className="password-input">
        <input
          {...input}
          id={id}
          type={visible ? 'text' : 'password'}
          aria-invalid={errors.length > 0 || undefined}
          aria-describedby={describedBy}
          spellCheck={false}
          autoCapitalize="none"
        />
        <button
          type="button"
          className="password-toggle"
          aria-label={visible ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
          aria-pressed={visible}
          onClick={() => setVisible((v) => !v)}
        >
          {visible ? 'Hide' : 'Show'}
        </button>
      </div>
      {hint && <p className="field-hint" id={`${id}-hint`}>{hint}</p>}
      {errors.length > 0 && (
        <ul className="field-errors" id={`${id}-errors`} role="alert">
          {errors.map((e) => <li key={e}>{e}</li>)}
        </ul>
      )}
    </div>
  )
}
