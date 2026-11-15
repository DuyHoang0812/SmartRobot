import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Ban, Check, KeyRound, Pencil, Plus, Shield } from 'lucide-react'
import { useAdminList } from '../../hooks/useAdminList'
import { useAuth } from '../../hooks/useAuth'
import type { AdminUser } from '../../types/admin'
import { ActiveFilter, ListControls, Pagination } from '../../components/admin/ListControls'
import { Feedback } from '../../components/admin/Feedback'
import { UserDialog } from '../../components/admin/UserDialog'
import type { UserAction } from '../../components/admin/UserDialog'

export function UsersPage() {
  const auth = useAuth()
  const cache = useQueryClient()
  const [draft, setDraft] = useState('')
  const [filters, setFilters] = useState({ q: '', role: '', is_active: '' })
  const [page, setPage] = useState(1)
  const [action, setAction] = useState<UserAction | null>(null)
  const [notice, setNotice] = useState('')
  const list = useAdminList<AdminUser>('users', page, filters)
  function filter(key: string, value: string) { setPage(1); setFilters({ ...filters, [key]: value }) }
  async function saved() {
    const self = action && action.kind !== 'create' && action.user.id === auth.user?.id
    setAction(null); setPage(1); setNotice('Đã lưu người dùng.')
    if (self) await auth.refreshUser().catch(() => {})
    await cache.invalidateQueries({ queryKey: ['admin-users'] })
  }
  return <>
    <div className="page-heading"><h1>Người dùng</h1><button className="primary-button" onClick={() => setAction({ kind: 'create' })}><Plus size={18} aria-hidden="true" />Thêm</button></div>
    {notice && <p role="status" className="success-message">{notice}</p>}
    <ListControls query={draft} setQuery={setDraft} onSearch={() => filter('q', draft.trim())} onReload={() => { void list.refetch() }}>
      <select className="filter-select" aria-label="Lọc role" value={filters.role} onChange={(event) => filter('role', event.target.value)}><option value="">Mọi role</option><option value="USER">USER</option><option value="ADMIN">ADMIN</option></select>
      <ActiveFilter value={filters.is_active} onChange={(value) => filter('is_active', value)} />
    </ListControls>
    <Feedback loading={list.isPending} error={list.error} empty={list.data?.items.length === 0} retry={() => { void list.refetch() }} />
    {list.data && !list.error && <>
      {list.data.items.length > 0 && <div className="table-scroll"><table className="admin-table"><thead><tr><th>Username</th><th>Email</th><th>Role</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>
        {list.data.items.map((user) => <tr key={user.id}>
          <td className="font-medium">{user.username}</td><td>{user.email}</td><td><span className="badge">{user.role}</span></td><td><span className={user.is_active ? 'badge-green' : 'badge'}>{user.is_active ? 'Hoạt động' : 'Vô hiệu hóa'}</span></td>
          <td><div className="flex gap-1">
            <button className="icon-button" aria-label={`Sửa ${user.username}`} onClick={() => setAction({ kind: 'edit', user })}><Pencil size={17} aria-hidden="true" /></button>
            <button className="icon-button" aria-label={`Đổi quyền ${user.username}`} onClick={() => setAction({ kind: 'role', user })}><Shield size={17} aria-hidden="true" /></button>
            <button className="icon-button" aria-label={`Đặt lại mật khẩu ${user.username}`} onClick={() => setAction({ kind: 'password', user })}><KeyRound size={17} aria-hidden="true" /></button>
            <button className="icon-button" aria-label={`${user.is_active ? 'Vô hiệu hóa' : 'Kích hoạt'} ${user.username}`} disabled={user.id === auth.user?.id && user.is_active} title={user.id === auth.user?.id ? 'Không thể tự vô hiệu hóa tài khoản' : undefined} onClick={() => setAction({ kind: 'status', user })}>{user.is_active ? <Ban size={17} aria-hidden="true" /> : <Check size={17} aria-hidden="true" />}</button>
          </div></td>
        </tr>)}
      </tbody></table></div>}
      <Pagination page={page} total={list.data.total} setPage={setPage} />
    </>}
    {action && <UserDialog action={action} onClose={() => setAction(null)} onSaved={saved} />}
  </>
}
