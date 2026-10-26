import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../api'
import { useAuth } from '../auth/AuthContext'
import PasswordField from '../components/PasswordField'
import { MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, PASSWORD_HINT } from '../passwordRules'

type Errors = Partial<Record<'first_name' | 'last_name' | 'email' | 'password' | 'confirm' | 'form', string[]>>

export default function CreateAccountPage() {
  const { user, signup } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const returnTo = (location.state as { from?: string } | null)?.from ?? '/'
  const [errors, setErrors] = useState<Errors>({})
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const password = String(form.get('password'))
    if (password.length < MIN_PASSWORD_LENGTH) {
      setErrors({ password: [`Use at least ${MIN_PASSWORD_LENGTH} characters.`] })
      return
    }
    if (password !== form.get('confirmPassword')) {
      setErrors({ confirm: ['Passwords do not match.'] })
      return
    }
    setErrors({})
    setSubmitting(true)
    try {
      await signup({
        first_name: String(form.get('firstName')).trim(),
        last_name: String(form.get('lastName')).trim(),
        email: String(form.get('email')).trim(),
        password,
      })
      navigate(returnTo, { replace: true })
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors({ [(err.field as keyof Errors) ?? 'form']: err.messages })
      } else {
        setErrors({ form: ['Something went wrong. Please try again in a moment.'] })
      }
      setSubmitting(false)
    }
  }

  if (user) {
    return (
      <div className="section container auth-page">
        <div className="auth-card">
          <h1 className="page-title">You're all set</h1>
          <p className="auth-note">You're logged in as <strong>{user.email}</strong>.</p>
          <Link to="/products" className="button button-primary button-block">Shop products</Link>
        </div>
      </div>
    )
  }

  const fieldErrors = (key: keyof Errors) =>
    errors[key] ? <ul className="field-errors" role="alert">{errors[key]!.map((m) => <li key={m}>{m}</li>)}</ul> : null

  return (
    <div className="section container auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1 className="page-title">Create Account</h1>
        <div className="field-row">
          <label className="field">
            <span>First name</span>
            <input name="firstName" autoComplete="given-name" required maxLength={50} aria-invalid={!!errors.first_name || undefined} />
            {fieldErrors('first_name')}
          </label>
          <label className="field">
            <span>Last name</span>
            <input name="lastName" autoComplete="family-name" required maxLength={50} aria-invalid={!!errors.last_name || undefined} />
            {fieldErrors('last_name')}
          </label>
        </div>
        <label className="field">
          <span>Email</span>
          <input type="email" name="email" autoComplete="email" required maxLength={254} aria-invalid={!!errors.email || undefined} />
          {fieldErrors('email')}
        </label>
        <PasswordField
          label="Password"
          name="password"
          autoComplete="new-password"
          required
          minLength={MIN_PASSWORD_LENGTH}
          maxLength={MAX_PASSWORD_LENGTH}
          hint={PASSWORD_HINT}
          errors={errors.password}
        />
        <PasswordField
          label="Confirm password"
          name="confirmPassword"
          autoComplete="new-password"
          required
          maxLength={MAX_PASSWORD_LENGTH}
          errors={errors.confirm}
        />
        {errors.form && <p className="form-error" role="alert">{errors.form.join(' ')}</p>}
        <button type="submit" className="button button-primary button-block" disabled={submitting}>
          {submitting ? 'Creating account…' : 'Create Account'}
        </button>
        <p className="auth-switch">
          Already have an account? <Link to="/login" state={location.state}>Log in</Link>
        </p>
      </form>
    </div>
  )
}
