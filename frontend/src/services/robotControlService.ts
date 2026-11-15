import { apiRequest } from './api'
import type { ControlState, LeaseGrant, LeaseView, Mode, MoveDirection, RobotCommand } from '../types/control'

export class RobotControlService {
  private grant: LeaseGrant | null = null
  private tail: Promise<unknown> = Promise.resolve()
  private intent = 0
  private clientSequence = 0
  private stopPromise: Promise<RobotCommand | undefined> | null = null
  private releasePromise: Promise<void> | null = null
  readonly base: string
  constructor(id: string) { this.base = `/robots/${encodeURIComponent(id)}/control` }
  state(signal?: AbortSignal) { return apiRequest<ControlState>(`${this.base}/state`, { signal }) }
  private enqueue<T>(operation: () => Promise<T>): Promise<T> {
    const result = this.tail.then(operation)
    this.tail = result.catch(() => {})
    return result
  }
  private async request<T>(path: string, body?: object): Promise<T> {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    const deadline = new Promise<never>((_, reject) => {
      timer = setTimeout(() => {
        controller.abort()
        reject(new DOMException('Control request timed out', 'TimeoutError'))
      }, 900)
    })
    try {
      return await Promise.race([deadline, apiRequest<T>(`${this.base}/${path}`, { method: 'POST',
        body: body ? JSON.stringify(body) : undefined, signal: controller.signal })])
    } finally { clearTimeout(timer) }
  }
  private credentials(grant: LeaseGrant) {
    return { control_session_id: grant.id, lease_token: grant.lease_token }
  }
  async acquire() {
    if (this.releasePromise) await this.releasePromise
    const grant = await this.enqueue(() => this.request<LeaseGrant>('acquire'))
    this.grant = grant; this.clientSequence = 0; this.intent += 1
    return grant
  }
  renew() {
    const grant = this.grant
    if (!grant) return Promise.reject(new Error('No lease'))
    return this.enqueue(() => this.request<LeaseView>('renew', this.credentials(grant)))
  }
  beginIntent() { return ++this.intent }
  move(direction: MoveDirection, intent: number) {
    const grant = this.grant
    const client_sequence = ++this.clientSequence
    const request_id = crypto.randomUUID()
    return this.enqueue(async () => {
      if (!grant || grant !== this.grant || intent !== this.intent) return undefined
      return this.request<RobotCommand>('move', { ...this.credentials(grant), direction, request_id, client_sequence })
    })
  }
  stop(): Promise<RobotCommand | undefined> {
    this.intent += 1 // Invalidate queued moves immediately, before waiting on an in-flight request.
    if (this.stopPromise) return this.stopPromise
    const grant = this.grant
    if (!grant) return Promise.resolve(undefined)
    const body = { ...this.credentials(grant), request_id: crypto.randomUUID(), client_sequence: ++this.clientSequence }
    this.stopPromise = this.enqueue(() => this.request<RobotCommand>('stop', body))
      .finally(() => { this.stopPromise = null })
    return this.stopPromise
  }
  async mode(mode: Mode) {
    await this.stop()
    const grant = this.grant
    if (!grant) throw new Error('No lease')
    const body = { ...this.credentials(grant), mode, request_id: crypto.randomUUID(), client_sequence: ++this.clientSequence }
    return this.enqueue(() => this.request<RobotCommand>('mode', body))
  }
  release(): Promise<void> {
    if (this.releasePromise) return this.releasePromise
    const grant = this.grant
    const stopped = this.stop()
    this.grant = null
    this.releasePromise = (async () => {
      await stopped.catch(() => {})
      if (grant) await this.enqueue(() => this.request<void>('release', this.credentials(grant)))
    })().finally(() => { this.releasePromise = null })
    return this.releasePromise
  }
  forget() { this.intent += 1; this.grant = null }
}
