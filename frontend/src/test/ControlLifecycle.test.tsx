import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { AuthContext } from '../contexts/auth-context'
import { useRobotControl } from '../hooks/useRobotControl'
import * as api from '../services/api'
import { controlState, FakeRobotSocket } from './controlFixtures'

let current = controlState()
let ttl = 10000
let fetchMock = vi.fn<typeof fetch>()
let client: QueryClient
const json = (value: unknown) => new Response(JSON.stringify(value), { status: 200 })
function Probe() {
  const control = useRobotControl('r1', true)
  return <>
    <button onClick={() => { void control.acquire() }}>Nhận</button>
    <button disabled={!control.canDrive} onPointerDown={() => control.start('FORWARD')} onPointerUp={control.stop}>Tiến</button>
    <span>{control.owns ? 'owned' : 'released'}</span>
  </>
}
async function advance(ms = 20) { await act(async () => { await vi.advanceTimersByTimeAsync(ms) }) }
async function mount(acquire = true) {
  const view = render(<AuthContext.Provider value={{ user: { id: 'viewer', username: 'operator', email: 'u@example.com', role: 'USER', is_active: true }, loading: false, error: '', login: vi.fn(), logout: vi.fn(), refreshUser: vi.fn() }}>
    <QueryClientProvider client={client}><Probe /></QueryClientProvider>
  </AuthContext.Provider>)
  await advance()
  await act(async () => { FakeRobotSocket.instances[0].open(); FakeRobotSocket.instances[0].frame(current) })
  if (!acquire) return view
  fireEvent.click(screen.getByRole('button', { name: 'Nhận' }))
  await advance()
  expect(screen.getByRole('button', { name: 'Tiến' })).toBeEnabled()
  return view
}
beforeEach(() => {
  vi.useFakeTimers()
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  current = controlState({ actual_mode: 'MANUAL', actual_movement: 'STOP', mode_pending: false, telemetry_fresh: true })
  ttl = 10000
  FakeRobotSocket.instances = []
  vi.stubGlobal('WebSocket', FakeRobotSocket)
  vi.spyOn(api, 'socketAccessToken').mockResolvedValue('memory-token')
  fetchMock = vi.fn<typeof fetch>().mockImplementation(async (url) => {
    if (String(url).endsWith('/state')) return json(current)
    if (String(url).endsWith('/acquire')) {
      current = { ...current, lease: { id: 'lease', owned: true, expires_at: new Date(Date.now() + ttl).toISOString() } }
      return json({ ...current.lease, lease_token: 'memory-secret', renew_after_ms: 2000 })
    }
    if (String(url).endsWith('/renew')) return json({ ...current.lease, expires_at: new Date(Date.now() + ttl).toISOString() })
    if (String(url).endsWith('/release')) return new Response(null, { status: 204 })
    return json({ command_id: 'accepted' })
  })
  vi.stubGlobal('fetch', fetchMock)
})
afterEach(async () => {
  cleanup()
  await advance()
  client.clear()
  vi.useRealTimers()
})

it('expires the local lease and disables controls without needing a server event', async () => {
  ttl = 300
  await mount()
  await advance(400)
  expect(screen.getByText('released')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Tiến' })).toBeDisabled()
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/release'))).toBe(true)
})

it('refreshes held movement at a bounded rate and stops refreshing after release', async () => {
  await mount()
  fireEvent.pointerDown(screen.getByRole('button', { name: 'Tiến' }))
  await advance(1000)
  const count = () => fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/move')).length
  expect(count()).toBeGreaterThanOrEqual(2)
  expect(count()).toBeLessThanOrEqual(5)
  fireEvent.pointerUp(screen.getByRole('button', { name: 'Tiến' }))
  await advance()
  const final = count()
  await advance(1000)
  expect(count()).toBe(final)
})

it('sends stop and release when unmounting with an active lease', async () => {
  const view = await mount()
  view.unmount()
  await advance()
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/stop'))).toBe(true)
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/release'))).toBe(true)
})

it('stops and releases after a failed movement request', async () => {
  await mount()
  fetchMock.mockImplementation(async (url) => {
    if (String(url).endsWith('/move')) throw new TypeError('Offline')
    if (String(url).endsWith('/release')) return new Response(null, { status: 204 })
    return json({ command_id: 'stop' })
  })
  fireEvent.pointerDown(screen.getByRole('button', { name: 'Tiến' }))
  await advance()
  expect(screen.getByText('released')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/release'))).toBe(true)
})

it('releases when the document becomes hidden', async () => {
  await mount()
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
  fireEvent(document, new Event('visibilitychange'))
  await advance()
  expect(screen.getByText('released')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/release'))).toBe(true)
})

it('releases a late acquisition response after the page has unmounted', async () => {
  const view = await mount(false)
  let resolve: (value: Response) => void = () => {}
  const delayed = new Promise<Response>((done) => { resolve = done })
  fetchMock.mockImplementation(async (url) => {
    if (String(url).endsWith('/acquire')) return delayed
    if (String(url).endsWith('/release')) return new Response(null, { status: 204 })
    return json({ command_id: 'stop' })
  })
  fireEvent.click(screen.getByRole('button', { name: 'Nhận' }))
  await advance()
  view.unmount()
  await advance()
  resolve(json({ id: 'late', owned: true, expires_at: new Date(Date.now() + ttl).toISOString(), lease_token: 'memory-secret', renew_after_ms: 2000 }))
  await advance()
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/release'))).toBe(true)
})
