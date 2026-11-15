import type { User } from './auth'
import type { RobotStatusValue } from './robots'

export interface AdminUser extends User {
  created_at: string
  updated_at: string
}

export interface Robot {
  id: string
  name: string
  device_id: string
  is_active: boolean
  is_simulated: boolean
  status: RobotStatusValue
  last_seen_at: string | null
  created_at: string
  updated_at: string
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

// One-time responses are kept only in the credential dialog, never in Query cache.
export interface CredentialResult {
  robot: Robot
  credential: string
}
