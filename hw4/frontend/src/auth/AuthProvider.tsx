import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import * as api from '../api'
import { AuthContext, type AuthState } from './AuthContext'

// The session itself lives in an HttpOnly cookie the page can't read; this only keeps
// the logged-in shopper's name and email for the header and forms.
export default function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<api.User | null>(null)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    api.fetchCurrentUser().then(setUser, () => setUser(null)).finally(() => setChecking(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const loggedIn = await api.login(email, password)
    setUser(loggedIn)
    return loggedIn
  }, [])

  const signup = useCallback(async (input: api.SignupInput) => {
    const created = await api.signup(input)
    setUser(created)
    return created
  }, [])

  const logout = useCallback(async () => {
    await api.logout().catch(() => {})
    setUser(null)
  }, [])

  const changePassword = useCallback(async (currentPassword: string, newPassword: string) => {
    const updated = await api.changePassword(currentPassword, newPassword)
    setUser(updated)
    return updated
  }, [])

  const value = useMemo<AuthState>(
    () => ({ user, checking, login, signup, logout, changePassword }),
    [user, checking, login, signup, logout, changePassword],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
