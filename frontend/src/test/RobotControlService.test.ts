import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { RobotControlService } from '../services/robotControlService'

const json = (value: unknown) => new Response(JSON.stringify(value), { status: 200 })
const grant = { id: 'lease', owned: true, expires_at: '2030-01-01T00:00:00Z', lease_token: 'memory-secret', renew_after_ms: 2000 }
let fetchMock = vi.fn<typeof fetch>()
beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>().mockImplementation(async (url) => json(String(url).endsWith('/acquire') ? grant : { command_id: 'cmd' }))
  vi.stubGlobal('fetch', fetchMock)
})
afterEach(() => { vi.useRealTimers() })

it('serializes requests and drops queued moves after a stop', async () => {
  const service = new RobotControlService('r1')
  await service.acquire()
  let finish: (response: Response) => void = () => {}
  fetchMock.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
  const intent = service.beginIntent()
  const first = service.move('FORWARD', intent)
  await Promise.resolve()
  const queued = service.move('FORWARD', intent)
  const stop = service.stop()
  expect(fetchMock).toHaveBeenCalledTimes(2)
  finish(json({ command_id: 'first' }))
  await Promise.all([first, queued, stop])
  expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/move'))).toHaveLength(1)
  expect(String(fetchMock.mock.calls.at(-1)?.[0])).toMatch(/\/stop$/)
  const sequences = fetchMock.mock.calls.slice(1).map(([, init]) => JSON.parse(String(init?.body)).client_sequence)
  expect(sequences[1]).toBeGreaterThan(sequences[0])
})

it('stops before switching mode and before releasing the lease', async () => {
  const service = new RobotControlService('r1')
  await service.acquire()
  await service.mode('AUTO')
  await service.release()
  expect(fetchMock.mock.calls.map(([url]) => String(url).split('/').at(-1))).toEqual(['acquire', 'stop', 'mode', 'stop', 'release'])
})

it('retains request IDs in serialized JSON without putting secrets in URLs', async () => {
  const service = new RobotControlService('r1')
  await service.acquire()
  await service.move('TURN_LEFT', service.beginIntent())
  const [url, init] = fetchMock.mock.calls[1]
  expect(String(url)).not.toContain(grant.lease_token)
  const body = JSON.parse(String(init?.body))
  expect(body.request_id).toBeTruthy()
  expect(body.control_session_id).toBe(grant.id)
  expect(body.client_sequence).toBe(1)
})

it('bounds a stalled request and allows the queued stop to proceed', async () => {
  const service = new RobotControlService('r1')
  await service.acquire()
  vi.useFakeTimers()
  fetchMock.mockImplementationOnce(() => new Promise(() => {}))
  const moving = service.move('FORWARD', service.beginIntent())
  const assertion = expect(moving).rejects.toThrow('Control request timed out')
  await Promise.resolve()
  const stopped = service.stop()
  await vi.advanceTimersByTimeAsync(950)
  await assertion
  await stopped
  expect(String(fetchMock.mock.calls.at(-1)?.[0])).toMatch(/\/stop$/)
})
