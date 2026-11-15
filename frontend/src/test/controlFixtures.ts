import type { ControlState } from '../types/control'

export function controlState(overrides: Partial<ControlState> = {}): ControlState {
  return { robot_id: 'online', status: 'ONLINE', lease: { id: null, owned: false, expires_at: null },
    sequence: 0, generation: 0, requested_mode: 'MANUAL', actual_mode: null, mode_pending: true,
    actual_movement: null, obstacle: null, distance_cm: null, buzzer: null, reported_at: null,
    telemetry_fresh: false, command: null, server_time: new Date().toISOString(), ...overrides }
}

export class FakeRobotSocket {
  static instances: FakeRobotSocket[] = []
  readonly url: string
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  onerror: (() => void) | null = null
  send = (...args: unknown[]) => { this.sent.push(args) }
  sent: unknown[][] = []
  constructor(url: string) { this.url = url; FakeRobotSocket.instances.push(this) }
  open() { this.onopen?.() }
  frame(data: ControlState) { this.onmessage?.({ data: JSON.stringify({ type: 'robot.state', data }) }) }
  disconnect(code = 1006) { this.onclose?.({ code }) }
  close() { this.onclose?.({ code: 1000 }) }
}
