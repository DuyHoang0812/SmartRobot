import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Ban, Check, KeyRound, Pencil, Plus } from 'lucide-react'
import { useAdminList } from '../../hooks/useAdminList'
import type { CredentialResult, Robot } from '../../types/admin'
import { ActiveFilter, ListControls, Pagination } from '../../components/admin/ListControls'
import { Feedback } from '../../components/admin/Feedback'
import { RobotDialog } from '../../components/admin/RobotDialog'
import type { RobotAction } from '../../components/admin/RobotDialog'
import { CredentialDialog } from '../../components/admin/CredentialDialog'
import { RobotStatus } from '../../components/robots/RobotStatus'

export function RobotsPage() {
  const cache = useQueryClient()
  const [draft, setDraft] = useState('')
  const [filters, setFilters] = useState({ q: '', status: '', is_active: '' })
  const [page, setPage] = useState(1)
  const [action, setAction] = useState<RobotAction | null>(null)
  const [secret, setSecret] = useState<CredentialResult | null>(null)
  const [notice, setNotice] = useState('')
  const list = useAdminList<Robot>('robots', page, filters)
  function filter(key: string, value: string) { setPage(1); setFilters({ ...filters, [key]: value }) }
  async function saved(credential?: CredentialResult) {
    setAction(null); setPage(1); setNotice('Đã lưu xe robot.')
    if (credential) setSecret(credential)
    await cache.invalidateQueries({ queryKey: ['admin-robots'] })
  }
  return <>
    <div className="page-heading"><h1>Xe robot</h1><button className="primary-button" onClick={() => setAction({ kind: 'create' })}><Plus size={18} aria-hidden="true" />Thêm</button></div>
    {notice && <p className="success-message" role="status">{notice}</p>}
    <ListControls query={draft} setQuery={setDraft} onSearch={() => filter('q', draft.trim())} onReload={() => { void list.refetch() }}>
      <select className="filter-select" aria-label="Kết nối" value={filters.status} onChange={(event) => filter('status', event.target.value)}><option value="">Mọi kết nối</option><option value="ONLINE">Online</option><option value="OFFLINE">Offline</option><option value="BUSY">Busy</option></select>
      <ActiveFilter value={filters.is_active} onChange={(value) => filter('is_active', value)} />
    </ListControls>
    <Feedback loading={list.isPending} error={list.error} empty={list.data?.items.length === 0} retry={() => { void list.refetch() }} />
    {list.data && !list.error && <>
      {list.data.items.length > 0 && <div className="table-scroll"><table className="admin-table"><thead><tr><th>Tên xe</th><th>Device ID</th><th>Kết nối</th><th>Trạng thái</th><th>Heartbeat cuối</th><th>Thao tác</th></tr></thead><tbody>
        {list.data.items.map((robot) => <tr key={robot.id}>
          <td className="font-medium">{robot.name}</td><td className="font-mono text-xs">{robot.device_id}</td>
          <td><RobotStatus status={robot.status} /></td>
          <td><span className={robot.is_active ? 'badge-green' : 'badge'}>{robot.is_active ? 'Hoạt động' : 'Vô hiệu hóa'}</span></td>
          <td>{robot.last_seen_at ? new Date(robot.last_seen_at).toLocaleString('vi-VN') : 'Chưa kết nối'}</td>
          <td><div className="flex gap-1">
            <button className="icon-button" aria-label={`Sửa ${robot.name}`} onClick={() => setAction({ kind: 'edit', robot })}><Pencil size={17} aria-hidden="true" /></button>
            <button className="icon-button" aria-label={`Xoay credential ${robot.name}`} onClick={() => setAction({ kind: 'rotate', robot })}><KeyRound size={17} aria-hidden="true" /></button>
            <button className="icon-button" aria-label={`${robot.is_active ? 'Vô hiệu hóa' : 'Kích hoạt'} ${robot.name}`} onClick={() => setAction({ kind: 'status', robot })}>{robot.is_active ? <Ban size={17} aria-hidden="true" /> : <Check size={17} aria-hidden="true" />}</button>
          </div></td>
        </tr>)}
      </tbody></table></div>}
      <Pagination page={page} total={list.data.total} setPage={setPage} />
    </>}
    {action && <RobotDialog action={action} onClose={() => setAction(null)} onSaved={saved} />}
    {secret && <CredentialDialog result={secret} onClose={() => setSecret(null)} />}
  </>
}
