import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { isRobotNotFound, useRobot } from '../hooks/useRobots'
import { useRobotControl } from '../hooks/useRobotControl'
import { RobotStatus } from '../components/robots/RobotStatus'
import { Feedback } from '../components/admin/Feedback'
import { ManualDPad } from '../components/control/ManualDPad'
import { ControlModeSelector } from '../components/control/ControlModeSelector'
import { ControlLeaseManager } from '../components/control/ControlLeaseManager'
import { ObstacleStatus } from '../components/control/ObstacleStatus'
import { CommandAcknowledgement } from '../components/control/CommandAcknowledgement'
import type { Direction } from '../types/control'

const movements: Record<Direction, string> = { FORWARD: 'Tiến', BACKWARD: 'Lùi', TURN_LEFT: 'Quay trái', TURN_RIGHT: 'Quay phải', STOP: 'Đã dừng' }
const dateFormat = new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeStyle: 'medium', timeZone: 'UTC' })

export function RobotControlPage() {
  const { id = '' } = useParams()
  const robot = useRobot(id)
  const control = useRobotControl(id, Boolean(robot.data && !robot.error))
  const state = control.state
  const online = (state?.status ?? robot.data?.status) !== 'OFFLINE'
  const connected = control.connection === 'connected'
  return <>
    <Link to="/dashboard" className="mb-6 inline-flex items-center gap-2 text-sm font-medium text-blue-600 hover:underline"><ArrowLeft size={17} aria-hidden="true" />Về Dashboard</Link>
    {isRobotNotFound(robot.error) || isRobotNotFound(control.queryError) ? <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h1 className="mb-3 text-2xl font-semibold">Không tìm thấy xe (404)</h1><p className="text-sm text-slate-600">Xe không tồn tại hoặc đã bị vô hiệu hóa.</p>
    </section> : <>
      <Feedback loading={robot.isPending} error={robot.error} empty={false} errorText="Không thể tải dữ liệu" retry={() => { void robot.refetch() }} />
      {robot.data && !robot.error && <>
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3"><h1 className="break-words text-2xl font-semibold">{robot.data.name}</h1><RobotStatus status={state?.status ?? robot.data.status} /></div>
          <ControlLeaseManager owns={control.owns} available={connected && online && state?.status !== 'BUSY'}
            pending={control.pending} onAcquire={() => { void control.acquire() }} onRelease={() => { void control.release() }} />
        </div>
        {(control.error || control.queryError) && <p role="alert" className="form-error mb-5">{control.error || 'Không thể tải trạng thái điều khiển'}<button className="ml-3 underline" onClick={control.retry}>Thử lại</button></p>}
        <div className="grid gap-5 lg:grid-cols-2">
          <section className="rounded-xl border border-slate-200 bg-white p-5 sm:p-7">
            <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
              <ControlModeSelector mode={state?.requested_mode ?? 'MANUAL'} disabled={!control.owns || !connected || !online || Boolean(state?.mode_pending) || control.pending}
                onChange={(mode) => { void control.mode(mode) }} />
              <span role="status" className="text-sm text-slate-500">{control.loading ? 'Đang tải…' : !connected ? 'Mất kết nối điều khiển' : !control.owns ? state?.status === 'BUSY' ? 'Xe đang bận' : 'Chưa nhận điều khiển' : state?.mode_pending ? 'Chờ thiết bị' : 'Đang giữ quyền'}</span>
            </div>
            <ManualDPad key={control.canDrive ? 'ready' : 'disabled'} disabled={!control.canDrive} onStart={control.start} onStop={control.stop} />
          </section>
          <section className="rounded-xl border border-slate-200 bg-white p-5 sm:p-7">
            <dl className="mb-6 grid gap-5 sm:grid-cols-2">
              <div><dt className="text-sm text-slate-500">Chế độ yêu cầu</dt><dd className="mt-1">{state ? state.requested_mode === 'MANUAL' ? 'Manual' : 'Auto' : 'Chưa có dữ liệu'}</dd></div>
              <div><dt className="text-sm text-slate-500">Chế độ thiết bị</dt><dd className="mt-1">{state?.telemetry_fresh && state.actual_mode ? state.actual_mode === 'MANUAL' ? 'Manual' : 'Auto' : 'Chưa xác nhận'}</dd></div>
              <div><dt className="text-sm text-slate-500">Tín hiệu động cơ</dt><dd className="mt-1">{state?.telemetry_fresh && state.actual_movement ? movements[state.actual_movement] : 'Chưa xác nhận'}</dd></div>
              <div><dt className="text-sm text-slate-500">Kết nối điều khiển</dt><dd className="mt-1">{connected ? 'Đã kết nối' : control.connection === 'connecting' ? 'Đang kết nối…' : 'Mất kết nối'}</dd></div>
              <div><dt className="text-sm text-slate-500">Lệnh backend</dt><dd className="mt-1">{control.accepted ? 'Đã nhận yêu cầu' : '—'}</dd></div>
              <CommandAcknowledgement state={state} />
            </dl>
            <p className="mb-4 text-sm text-slate-500">Xe chưa có cảm biến tốc độ bánh xe. Tín hiệu động cơ cho biết hướng xuất ra mạch, chưa xác nhận xe đã di chuyển.</p>
            <ObstacleStatus state={state} />
            <dl className="mt-6 grid gap-5 border-t border-slate-100 pt-5 text-sm sm:grid-cols-2">
              <div><dt className="text-slate-500">Device ID</dt><dd className="mt-1 break-all font-mono">{robot.data.device_id}</dd></div>
              <div><dt className="text-slate-500">Trạng thái kích hoạt</dt><dd className="mt-1">{robot.data.is_active ? 'Hoạt động' : 'Vô hiệu hóa'}</dd></div>
              <div><dt className="text-slate-500">Heartbeat cuối</dt><dd className="mt-1">{robot.data.last_seen_at ? <time dateTime={robot.data.last_seen_at}>{dateFormat.format(new Date(robot.data.last_seen_at))} UTC</time> : 'Chưa kết nối'}</dd></div>
            </dl>
          </section>
        </div>
      </>}
    </>}
  </>
}
