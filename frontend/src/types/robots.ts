export type RobotStatusValue = 'ONLINE' | 'OFFLINE' | 'BUSY'

export interface UserRobot {
  id: string
  name: string
  device_id: string
  is_active: boolean
  last_seen_at: string | null
  status: RobotStatusValue
  available: boolean
}

export interface RobotFiltersValue {
  q: string
  status: '' | RobotStatusValue
}
