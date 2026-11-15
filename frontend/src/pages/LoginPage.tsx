import { useState } from 'react'
import type { FormEvent } from 'react'
import { Bot, Eye, EyeOff, LoaderCircle } from 'lucide-react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { errorMessage } from '../services/api'
import { Loading } from '../components/Loading'

export function LoginPage() {
  const auth = useAuth()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [visible, setVisible] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  if (auth.loading) return <Loading />
  if (auth.user) return <Navigate to="/dashboard" replace />

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!identifier.trim()) { setError('Vui lòng nhập tài khoản.'); return }
    const passwordLength = Array.from(password).length
    if (passwordLength < 12 || passwordLength > 128) {
      setError('Mật khẩu phải có từ 12 đến 128 ký tự.'); return
    }
    setError('')
    setPending(true)
    try { await auth.login(identifier.trim(), password) }
    catch (failure) { setError(errorMessage(failure)) }
    finally { setPending(false) }
  }

  return <main className="flex min-h-svh items-center justify-center px-5 py-10">
    <section className="w-full max-w-[400px] rounded-2xl border border-slate-200 bg-white p-7 shadow-sm sm:p-9">
      <div className="mb-9 flex items-center gap-3">
        <span className="rounded-xl bg-blue-600 p-2.5 text-white"><Bot size={25} aria-hidden="true" /></span>
        <h1 className="text-2xl font-semibold tracking-tight">SmartRobot</h1>
      </div>
      <form onSubmit={(event) => { void submit(event) }} noValidate className="space-y-5" aria-label="Đăng nhập">
        <div>
          <label className="field-label" htmlFor="identifier">Username hoặc Email</label>
          <input id="identifier" name="username" autoComplete="username" autoCapitalize="none"
            spellCheck={false} maxLength={254} className="field-input" value={identifier}
            onChange={(event) => setIdentifier(event.target.value)} disabled={pending}
            aria-describedby={error ? 'login-error' : undefined} required />
        </div>
        <div>
          <label className="field-label" htmlFor="password">Mật khẩu</label>
          <div className="relative">
            <input id="password" name="password" autoComplete="current-password" maxLength={256}
              type={visible ? 'text' : 'password'} className="field-input pr-12" value={password}
              onChange={(event) => setPassword(event.target.value)} disabled={pending}
              aria-describedby={error ? 'login-error' : undefined} required />
            <button type="button" aria-label={visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
              aria-pressed={visible} onClick={() => setVisible(!visible)}
              className="absolute inset-y-0 right-0 flex w-12 items-center justify-center rounded-lg text-slate-500 hover:text-blue-600">
              {visible ? <EyeOff size={19} aria-hidden="true" /> : <Eye size={19} aria-hidden="true" />}
            </button>
          </div>
        </div>
        {(error || auth.error) && <p id="login-error" role="alert" className="rounded-lg bg-red-50 px-3 py-2.5 text-sm text-red-700">{error || auth.error}</p>}
        <button type="submit" disabled={pending} className="primary-button w-full">
          {pending && <LoaderCircle size={18} className="animate-spin" aria-hidden="true" />}
          {pending ? 'Đang đăng nhập…' : 'Đăng nhập'}
        </button>
      </form>
    </section>
  </main>
}
