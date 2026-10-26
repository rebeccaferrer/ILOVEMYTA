import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../api'
import { useAuth } from '../auth/AuthContext'
import PasswordField from '../components/PasswordField'

export default function LoginPage() {
  const { user, login, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const returnTo = (location.state as { from?: string } | null)?.from ?? '/'
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    setError('')
    setSubmitting(true)
    try {
      const loggedIn = await login(String(form.get('email')).trim(), String(form.get('password')))
      if (loggedIn.must_change_password) {
        navigate('/change-password', { replace: true, state: { from: returnTo } })
      } else {
        navigate(returnTo, { replace: true })
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.messages[0] : 'Something went wrong. Please try again in a moment.')
      setSubmitting(false)
    }
  }

  if (user) {
    return (
      <div className="section container auth-page">
        <div className="auth-card">
          <h1 className="page-title">You're logged in</h1>
          <p className="auth-note">Logged in as <strong>{user.email}</strong>.</p>
          <Link to="/products" className="button button-primary button-block">Shop products</Link>
          <button type="button" className="button button-secondary button-block" onClick={() => logout()}>Log out</button>
        </div>
      </div>
    )
  }

  return (
    <div className="section container auth-page">
      <form className="auth-card" onSubmit={handleSubmit} noValidate={false}>
        <h1 className="page-title">Log In</h1>
        <label className="field">
          <span>Email</span>
          <input type="email" name="email" autoComplete="username" required maxLength={254} />
        </label>
        <PasswordField label="Password" name="password" autoComplete="current-password" required maxLength={128} />
        {error && <p className="form-error" role="alert">{error}</p>}
        <button type="submit" className="button button-primary button-block" disabled={submitting}>
          {submitting ? 'Logging in…' : 'Log In'}
        </button>
        <p className="auth-switch">
          New here? <Link to="/create-account" state={location.state}>Create an account</Link>
        </p>
      </form>
    </div>
  )
}
