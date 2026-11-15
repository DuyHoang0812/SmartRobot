import { createContext } from 'react'
import type { User } from '../types/auth'

export interface AuthContextValue {
  user: User | null
  loading: boolean
  error: string
  login: (identifier: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
