import { createContext, useContext } from 'react'
import type { SignupInput, User } from '../api'

export type AuthState = {
  user: User | null
  /** True until we've asked the server whether someone is already logged in. */
  checking: boolean
  login: (email: string, password: string) => Promise<User>
  signup: (input: SignupInput) => Promise<User>
  logout: () => Promise<void>
  changePassword: (currentPassword: string, newPassword: string) => Promise<User>
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const auth = useContext(AuthContext)
  if (!auth) throw new Error('useAuth must be used inside <AuthProvider>')
  return auth
}
