import type { ControlState } from '../../types/control'

const labels = { RECEIVED: 'Đã nhận lệnh', APPLIED: 'Đã áp dụng yêu cầu',
  REJECTED: 'Thiết bị từ chối', FAILED: 'Thiết bị báo lỗi' }

export function CommandAcknowledgement({ state }: { state?: ControlState }) {
  const ack = state?.acknowledgement
  const failed = ack?.status === 'FAILED' || ack?.status === 'REJECTED'
  const current = ack && (failed || ack.sequence === state?.sequence)
  return <div><dt className="text-sm text-slate-500">Xác nhận thiết bị</dt>
    <dd className={`mt-1 ${failed ? 'text-red-700' : ''}`} role={failed ? 'alert' : undefined}>
      {current ? labels[ack.status] : 'Chưa xác nhận'}
    </dd>
  </div>
}
