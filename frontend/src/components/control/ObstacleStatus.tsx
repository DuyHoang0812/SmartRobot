import type { ControlState } from '../../types/control'

export function ObstacleStatus({ state }: { state: ControlState | undefined }) {
  const labels = { CLEAR: 'Phía trước thông thoáng', BLOCKED: 'Có vật cản', SENSOR_ERROR: 'Lỗi cảm biến' }
  const fresh = state?.telemetry_fresh
  return <dl className="grid gap-5 sm:grid-cols-2">
    <div><dt className="text-sm text-slate-500">Khoảng cách</dt><dd className="mt-1 font-medium">{fresh && state?.distance_cm != null ? `${state.distance_cm} cm` : '—'}</dd></div>
    <div><dt className="text-sm text-slate-500">Vật cản</dt><dd className={`mt-1 font-medium ${fresh && state?.obstacle && state.obstacle !== 'CLEAR' ? 'text-red-700' : ''}`}>
      {fresh && state?.obstacle ? labels[state.obstacle] : 'Chưa có dữ liệu'}
    </dd></div>
    <div><dt className="text-sm text-slate-500">Buzzer</dt><dd className="mt-1">{fresh && state?.buzzer != null ? state.buzzer ? 'Bật' : 'Tắt' : '—'}</dd></div>
  </dl>
}
