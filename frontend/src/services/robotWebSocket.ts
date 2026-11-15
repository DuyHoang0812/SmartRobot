import { refreshSession, socketAccessToken } from './api'
import type { ControlState, SocketStatus } from '../types/control'

export class RobotWebSocket {
  private socket: WebSocket | null = null
  private retry: ReturnType<typeof setTimeout> | null = null
  private watchdog: ReturnType<typeof setTimeout> | null = null
  private stopped = false
  private attempt = 0
  private readonly id: string
  private readonly state: (state: ControlState) => void
  private readonly status: (status: SocketStatus) => void
  private readonly disconnected: () => void
  constructor(id: string, state: (state: ControlState) => void,
    status: (status: SocketStatus) => void, disconnected: () => void) {
    this.id = id; this.state = state; this.status = status; this.disconnected = disconnected
  }

  async start() {
    if (this.stopped) return
    this.status('connecting')
    try {
      const token = await socketAccessToken()
      if (this.stopped) return
      const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:'
      const socket = new WebSocket(`${scheme}//${location.host}/api/v1/ws/robots/${encodeURIComponent(this.id)}`)
      this.socket = socket
      socket.onopen = () => {
        if (this.stopped) return
        socket.send(JSON.stringify({ type: 'authenticate', access_token: token }))
        this.armWatchdog(socket)
      }
      socket.onmessage = (event) => {
        if (this.stopped || socket !== this.socket) return
        try {
          const message = JSON.parse(String(event.data))
          if (message.type === 'robot.state') {
            this.attempt = 0; this.state(message.data as ControlState); this.status('connected')
          }
          if (message.type === 'ping' || message.type === 'robot.state') this.armWatchdog(socket)
        } catch { this.fail(socket) }
      }
      socket.onerror = () => this.fail(socket)
      socket.onclose = (event) => {
        if (this.stopped || socket !== this.socket) return
        this.clearWatchdog(); this.status('disconnected'); this.disconnected()
        if (event.code === 4003 || event.code === 1008) return
        const delay = Math.min(500 * 2 ** this.attempt++, 5000)
        this.retry = setTimeout(() => {
          void (async () => {
            if (event.code === 4001) await refreshSession()
            await this.start()
          })().catch(() => { this.status('disconnected') })
        }, delay)
      }
    } catch {
      if (!this.stopped) {
        this.status('disconnected'); this.disconnected()
        this.retry = setTimeout(() => { void this.start() }, Math.min(500 * 2 ** this.attempt++, 5000))
      }
    }
  }
  private clearWatchdog() { if (this.watchdog) clearTimeout(this.watchdog) }
  private fail(socket: WebSocket) {
    if (this.stopped || socket !== this.socket) return
    this.clearWatchdog(); this.status('disconnected'); this.disconnected(); socket.close()
  }
  private armWatchdog(socket: WebSocket) {
    this.clearWatchdog()
    this.watchdog = setTimeout(() => this.fail(socket), 4000)
  }
  close() {
    this.stopped = true
    if (this.retry) clearTimeout(this.retry)
    this.clearWatchdog()
    this.socket?.close()
    this.socket = null
  }
}
