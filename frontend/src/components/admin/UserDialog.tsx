import { useState } from 'react'
import type { FormEvent } from 'react'
import { Modal } from './Modal'
import { apiRequest, errorMessage } from '../../services/api'
import type { AdminUser } from '../../types/admin'

export type UserAction = { kind: 'create' } | { kind: 'edit' | 'role' | 'status' | 'password'; user: AdminUser }
const titles = { create: 'Thêm người dùng', edit: 'Sửa người dùng', role: 'Đổi quyền', status: 'Trạng thái tài khoản', password: 'Đặt lại mật khẩu' }

export function UserDialog({ action, onClose, onSaved }: {
  action: UserAction; onClose: () => void; onSaved: () => Promise<void>
}) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const target = action.kind === 'create' ? null : action.user
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const password = String(data.get('password') ?? '')
    if (action.kind === 'create' || action.kind === 'password') {
      if (Array.from(password).length < 12 || Array.from(password).length > 128) {
        setError('Mật khẩu phải có từ 12 đến 128 ký tự.'); return
      }
      if (password !== data.get('confirmation')) { setError('Mật khẩu nhập lại không khớp.'); return }
    }
    const base = '/admin/users'
    let path = target ? `${base}/${target.id}` : base
    let body: object
    if (action.kind === 'role') { path += '/role'; body = { role: data.get('role') } }
    else if (action.kind === 'status') { path += '/status'; body = { is_active: !action.user.is_active } }
    else if (action.kind === 'password') { path += '/reset-password'; body = { password } }
    else {
      body = { username: String(data.get('username')).trim(), email: String(data.get('email')).trim(),
        ...(action.kind === 'create' ? { password, role: data.get('role') } : {}) }
    }
    setPending(true); setError('')
    try {
      await apiRequest(path, { method: action.kind === 'create' || action.kind === 'password' ? 'POST' : 'PATCH', body: JSON.stringify(body) })
      await onSaved()
    } catch (failure) { setError(errorMessage(failure)) }
    finally { setPending(false) }
  }
  return <Modal title={titles[action.kind]} onClose={onClose} busy={pending}>
    <form onSubmit={(event) => { void submit(event) }} className="space-y-4">
      {(action.kind === 'create' || action.kind === 'edit') && <>
        <div><label className="field-label" htmlFor="u-name">Username</label><input className="field-input" id="u-name" name="username" defaultValue={target?.username} pattern="[A-Za-z0-9_.\-]{3,64}" maxLength={64} required disabled={pending} autoComplete="off" /></div>
        <div><label className="field-label" htmlFor="u-email">Email</label><input className="field-input" id="u-email" name="email" type="email" defaultValue={target?.email} maxLength={254} required disabled={pending} autoComplete="off" /></div>
      </>}
      {(action.kind === 'create' || action.kind === 'role') && <div>
        <label className="field-label" htmlFor="u-role">Role</label><select className="field-input" id="u-role" name="role" defaultValue={target?.role ?? 'USER'} disabled={pending}><option value="USER">USER</option><option value="ADMIN">ADMIN</option></select>
      </div>}
      {(action.kind === 'create' || action.kind === 'password') && <>
        {action.kind === 'password' && <p className="text-sm text-slate-600">Các phiên đăng nhập của {target?.username} sẽ kết thúc.</p>}
        <div><label className="field-label" htmlFor="u-password">Mật khẩu mới</label><input className="field-input" id="u-password" name="password" type="password" autoComplete="new-password" maxLength={256} required disabled={pending} /></div>
        <div><label className="field-label" htmlFor="u-confirm">Nhập lại mật khẩu</label><input className="field-input" id="u-confirm" name="confirmation" type="password" autoComplete="new-password" maxLength={256} required disabled={pending} /></div>
      </>}
      {action.kind === 'role' && <p className="text-sm text-slate-600">Thay đổi quyền của {target?.username}?</p>}
      {action.kind === 'status' && <p className="text-sm text-slate-600">{action.user.is_active ? 'Vô hiệu hóa' : 'Kích hoạt'} {action.user.username}?{action.user.is_active && ' Các phiên đăng nhập và điều khiển sẽ kết thúc.'}</p>}
      {error && <p role="alert" className="form-error">{error}</p>}
      <div className="modal-actions"><button type="button" className="secondary-button" disabled={pending} onClick={onClose}>Hủy</button><button className="primary-button" disabled={pending}>{pending ? 'Đang lưu…' : action.kind === 'create' ? 'Tạo' : 'Lưu'}</button></div>
    </form>
  </Modal>
}
