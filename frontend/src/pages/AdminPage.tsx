import { useEffect, useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import { apiRequest, errorMessage } from '../services/api'
import type { User } from '../types/auth'

export function AdminPage() {
  const [status, setStatus] = useState('Đang kiểm tra…')
  const [error, setError] = useState(false)
  useEffect(() => {
    let active = true
    void apiRequest<User>('/admin/check').then(() => {
      if (active) setStatus('Quyền quản trị đã được xác nhận.')
    }).catch((failure: unknown) => {
      if (active) { setError(true); setStatus(errorMessage(failure)) }
    })
    return () => { active = false }
  }, [])
  return <>
    <h1 className="mb-6 text-2xl font-semibold">Quản trị</h1>
    <p role={error ? 'alert' : 'status'} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-6">
      <ShieldCheck className={error ? 'text-red-600' : 'text-blue-600'} aria-hidden="true" />{status}
    </p>
  </>
}
