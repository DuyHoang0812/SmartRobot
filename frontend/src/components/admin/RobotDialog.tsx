import { useState } from 'react'
import type { FormEvent } from 'react'
import { Modal } from './Modal'
import { apiRequest, errorMessage } from '../../services/api'
import type { CredentialResult, Robot } from '../../types/admin'

export type RobotAction = { kind: 'create' } | { kind: 'edit' | 'status' | 'rotate'; robot: Robot }
const titles = { create: 'Thêm xe robot', edit: 'Sửa xe robot', status: 'Trạng thái xe', rotate: 'Xoay credential' }

export function RobotDialog({ action, onClose, onSaved }: {
  action: RobotAction; onClose: () => void; onSaved: (credential?: CredentialResult) => Promise<void>
}) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const robot = action.kind === 'create' ? null : action.robot
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    let path = '/admin/robots' + (robot ? `/${robot.id}` : '')
    let body: object | undefined
    if (action.kind === 'status') { path += '/status'; body = { is_active: !action.robot.is_active } }
    else if (action.kind === 'rotate') path += '/credentials/rotate'
    else body = { name: String(data.get('name')).trim(), device_id: String(data.get('device_id')).trim() }
    setPending(true); setError('')
    try {
      const result = await apiRequest<CredentialResult>(path, { method: action.kind === 'create' || action.kind === 'rotate' ? 'POST' : 'PATCH', body: body ? JSON.stringify(body) : undefined })
      await onSaved(action.kind === 'create' || action.kind === 'rotate' ? result : undefined)
    } catch (failure) { setError(errorMessage(failure)) }
    finally { setPending(false) }
  }
  return <Modal title={titles[action.kind]} onClose={onClose} busy={pending}>
    <form onSubmit={(event) => { void submit(event) }} className="space-y-4">
      {(action.kind === 'create' || action.kind === 'edit') && <>
        <div><label className="field-label" htmlFor="r-name">Tên xe</label><input id="r-name" className="field-input" name="name" defaultValue={robot?.name} maxLength={120} required disabled={pending} /></div>
        <div><label className="field-label" htmlFor="r-device">Device ID</label><input id="r-device" className="field-input" name="device_id" defaultValue={robot?.device_id} maxLength={128} pattern="[A-Za-z0-9_.:\-]{3,128}" required disabled={pending} autoComplete="off" /></div>
        {action.kind === 'edit' && <p className="text-sm text-slate-500">Đổi Device ID yêu cầu cấu hình lại thiết bị.</p>}
      </>}
      {action.kind === 'rotate' && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Credential cũ sẽ bị thu hồi ngay. Thiết bị cần được cấu hình lại.</p>}
      {action.kind === 'status' && <p className="text-sm text-slate-600">{action.robot.is_active ? 'Vô hiệu hóa' : 'Kích hoạt'} {action.robot.name}?{action.robot.is_active && ' Kết nối và phiên điều khiển hiện tại sẽ mất hiệu lực.'}</p>}
      {error && <p role="alert" className="form-error">{error}</p>}
      <div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose} disabled={pending}>Hủy</button><button className="primary-button" disabled={pending}>{pending ? 'Đang lưu…' : action.kind === 'create' ? 'Tạo' : action.kind === 'rotate' ? 'Xoay' : 'Lưu'}</button></div>
    </form>
  </Modal>
}
