import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../api'
import { useAuth } from '../auth/AuthContext'
import PasswordField from '../components/PasswordField'
import { MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, PASSWORD_HINT } from '../passwordRules'

type Errors = Partial<Record<'current_password' | 'new_password' | 'confirm' | 'form', string[]>>

export default function ChangePasswordPage() {
  const { user, checking, changePassword, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const returnTo = (location.state as { from?: string } | null)?.from ?? '/'
  const [errors, setErrors] = useState<Errors>({})
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)

  if (checking) return null
  if (!user) return <Navigate to="/login" replace state={{ from: '/change-password' }} />

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const newPassword = String(form.get('newPassword'))
    if (newPassword.length < MIN_PASSWORD_LENGTH) {
      setErrors({ new_password: [`Use at least ${MIN_PASSWORD_LENGTH} characters.`] })
      return
    }
    if (newPassword !== form.get('confirmPassword')) {
      setErrors({ confirm: ['Passwords do not match.'] })
      return
    }
    setErrors({})
    setSubmitting(true)
    try {
      await changePassword(String(form.get('currentPassword')), newPassword)
      setDone(true)
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors({ [(err.field as keyof Errors) ?? 'form']: err.messages })
      } else {
        setErrors({ form: ['Something went wrong. Please try again in a moment.'] })
      }
      setSubmitting(false)
    }
  }

  if (done) {
    return (
      <div className="section container auth-page">
        <div className="auth-card">
          <h1 className="page-title">Password changed</h1>
          <p className="auth-note">Your new password is saved, and any other devices have been logged out.</p>
          <button type="button" className="button button-primary button-block" onClick={() => navigate(returnTo, { replace: true })}>
            Continue
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="section container auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1 className="page-title">{user.must_change_password ? 'Choose a New Password' : 'Change Password'}</h1>
        {user.must_change_password && (
          <p className="auth-notice" role="status">
            Our password rules are stricter now, and your current password doesn't meet them.
            Please choose a new one to continue.
          </p>
        )}
        <PasswordField
          label="Current password"
          name="currentPassword"
          autoComplete="current-password"
          required
          maxLength={MAX_PASSWORD_LENGTH}
          errors={errors.current_password}
        />
        <PasswordField
          label="New password"
          name="newPassword"
          autoComplete="new-password"
          required
          minLength={MIN_PASSWORD_LENGTH}
          maxLength={MAX_PASSWORD_LENGTH}
          hint={PASSWORD_HINT}
          errors={errors.new_password}
        />
        <PasswordField
          label="Confirm new password"
          name="confirmPassword"
          autoComplete="new-password"
          required
          maxLength={MAX_PASSWORD_LENGTH}
          errors={errors.confirm}
        />
        {errors.form && <p className="form-error" role="alert">{errors.form.join(' ')}</p>}
        <button type="submit" className="button button-primary button-block" disabled={submitting}>
          {submitting ? 'Saving…' : 'Save New Password'}
        </button>
        {user.must_change_password && (
          <button type="button" className="button button-secondary button-block" onClick={() => logout()}>
            Log out instead
          </button>
        )}
      </form>
    </div>
  )
}
