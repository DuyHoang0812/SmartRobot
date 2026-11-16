import type { RobotStatusValue } from './robots'

export type Mode = 'MANUAL' | 'AUTO'
export type MoveDirection = 'FORWARD' | 'BACKWARD' | 'TURN_LEFT' | 'TURN_RIGHT'
export type Direction = MoveDirection | 'STOP'
export type Obstacle = 'CLEAR' | 'BLOCKED' | 'SENSOR_ERROR'
export type SocketStatus = 'connecting' | 'connected' | 'disconnected'

export interface LeaseView { id: string | null; owned: boolean; expires_at: string | null }
export interface LeaseGrant extends LeaseView { id: string; lease_token: string; renew_after_ms: number }
export interface RobotCommand {
  command_id: string; robot_id: string; control_session_id: string; sequence: number;
  generation: number; kind: 'MOVE' | 'STOP' | 'MODE' | 'KEEPALIVE'; mode: Mode;
  direction: Direction; issued_at: string; expires_at: string;
  status: 'ACCEPTED' | 'RECEIVED' | 'EXECUTED' | 'APPLIED' | 'FAILED' | 'REJECTED' | 'SUPERSEDED' | 'EXPIRED'
  acknowledgement?: CommandAcknowledgementValue | null; acknowledged_at?: string | null
}
export type CommandAcknowledgementValue = 'RECEIVED' | 'APPLIED' | 'REJECTED' | 'FAILED'
export interface CommandAcknowledgementState { sequence: number; status: CommandAcknowledgementValue; acknowledged_at: string }
export interface ControlState {
  robot_id: string; status: RobotStatusValue; lease: LeaseView; sequence: number; generation: number;
  requested_mode: Mode; actual_mode: Mode | null; mode_pending: boolean;
  actual_movement: Direction | null; obstacle: Obstacle | null; distance_cm: number | null;
  buzzer: boolean | null; reported_at: string | null; telemetry_fresh: boolean;
  command: RobotCommand | null; server_time: string
  acknowledgement?: CommandAcknowledgementState | null
}
