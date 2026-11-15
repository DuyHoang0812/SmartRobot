import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { AuthContext } from './auth-context'
import * as api from '../services/api'
import type { User } from '../types/auth'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const channel = useRef<BroadcastChannel | null>(null)

  useEffect(() => {
    let active = true
    const unsubscribe = api.onSessionExpired(() => { if (active) setUser(null) })
    if ('BroadcastChannel' in window) {
      const broadcast = new BroadcastChannel('smartrobot-auth')
      channel.current = broadcast
      broadcast.onmessage = (event) => {
        if (event.data === 'logout') api.clearSession()
      }
    }
    void api.refreshSession().then(api.getMe).then((current) => {
      if (active) setUser(current)
    }).catch((failure: unknown) => {
      if (active && !(failure instanceof api.ApiError && [401, 403].includes(failure.status))) {
        setError(api.errorMessage(failure))
      }
    }).finally(() => { if (active) setLoading(false) })
    return () => {
      active = false
      unsubscribe()
      channel.current?.close()
      channel.current = null
    }
  }, [])

  async function login(identifier: string, password: string) {
    const current = await api.login(identifier, password)
    setUser(current)
    setError('')
  }

  async function logout() {
    await api.logout()
    setUser(null)
    channel.current?.postMessage('logout')
  }

  async function refreshUser() {
    setUser(await api.getMe())
  }

  return <AuthContext.Provider value={{ user, loading, error, login, logout, refreshUser }}>
    {children}
  </AuthContext.Provider>
}
