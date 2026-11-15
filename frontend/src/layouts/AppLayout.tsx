import { useState } from 'react'
import { Bot, LayoutDashboard, LogOut, ShieldCheck } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { errorMessage } from '../services/api'

export function AppLayout() {
  const { user, logout } = useAuth()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  async function handleLogout() {
    setPending(true)
    setError('')
    try { await logout() } catch (failure) { setError(errorMessage(failure)) }
    finally { setPending(false) }
  }
  return <div className="min-h-svh">
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-4">
        <span className="flex items-center gap-2 text-lg font-semibold"><Bot className="text-blue-600" aria-hidden="true" />SmartRobot</span>
        <div className="flex items-center gap-4">
          <span className="max-w-36 truncate text-sm text-slate-600">{user?.username}</span>
          <button className="secondary-button" onClick={() => { void handleLogout() }} disabled={pending}>
            <LogOut size={17} aria-hidden="true" />{pending ? 'Đang thoát…' : 'Đăng xuất'}
          </button>
        </div>
        <nav className="flex w-full gap-2" aria-label="Điều hướng">
          <NavLink className="nav-link" to="/dashboard"><LayoutDashboard size={18} aria-hidden="true" />Tổng quan</NavLink>
          {user?.role === 'ADMIN' && <NavLink className="nav-link" to="/admin"><ShieldCheck size={18} aria-hidden="true" />Quản trị</NavLink>}
        </nav>
      </div>
    </header>
    <main className="mx-auto max-w-7xl px-5 py-8">
      {error && <p role="alert" className="mb-5 text-sm text-red-700">{error}</p>}
      <Outlet />
    </main>
  </div>
}
