export function ControlLeaseManager({ owns, available, pending, onAcquire, onRelease }: {
  owns: boolean; available: boolean; pending: boolean; onAcquire: () => void; onRelease: () => void
}) {
  return owns ? <button className="secondary-button" disabled={pending} onClick={onRelease}>Thoát điều khiển</button>
    : <button className="primary-button" disabled={!available || pending} onClick={onAcquire}>
      {pending ? 'Đang yêu cầu…' : 'Nhận điều khiển'}
    </button>
}
