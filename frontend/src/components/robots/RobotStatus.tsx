import type { RobotStatusValue } from '../../types/robots'

const labels = { ONLINE: 'Online', OFFLINE: 'Offline', BUSY: 'Busy' }
const styles = { ONLINE: 'badge-green', OFFLINE: 'badge', BUSY: 'badge-blue' }

export function RobotStatus({ status }: { status: RobotStatusValue }) {
  return <span className={styles[status]}>{labels[status]}</span>
}
