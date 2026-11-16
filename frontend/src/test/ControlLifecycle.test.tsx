import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { AuthContext } from '../contexts/auth-context'
import { useRobotControl } from '../hooks/useRobotControl'
import * as api from '../services/api'
import { controlState, FakeRobotSocket } from './controlFixtures'

let current = controlState()
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
  FakeRobotSocket.instances = []
  vi.stubGlobal('WebSocket', FakeRobotSocket)
  vi.spyOn(api, 'socketAccessToken').mockResolvedValue('memory-token')
  fetchMock = vi.fn<typeof fetch>().mockImplementation(async (url) => {
    if (String(url).endsWith('/state')) return json(current)
    if (String(url).endsWith('/acquire')) {
      current = { ...current, lease: { id: 'lease', owned: true, expires_at: null } }
      return json({ ...current.lease, lease_token: 'memory-secret', renew_after_ms: 2000 })
    }
    if (String(url).endsWith('/renew')) return json({ ...current.lease, expires_at: null })
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

it('keeps an idle borrow beyond the old timeout without a server expiry', async () => {
  await mount()
  for (let i = 0; i < 8; i++) {
    await act(async () => FakeRobotSocket.instances[0].frame({ ...current, server_time: new Date().toISOString() }))
    await advance(2000)
  }
  expect(screen.getByText('owned')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Tiến' })).toBeEnabled()
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/release'))).toBe(false)
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

it('does not send a stop before the first move and sends one on release', async () => {
  await mount()
  const stops = () => fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/stop')).length
  const before = stops()
  fireEvent.pointerDown(screen.getByRole('button', { name: 'Tiến' }))
  await advance()
  expect(stops()).toBe(before)
  fireEvent.pointerUp(screen.getByRole('button', { name: 'Tiến' }))
  await advance()
  expect(stops()).toBe(before + 1)
})

it('does not cancel Auto when an idle Manual pad becomes disabled', async () => {
  await mount()
  const before = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/stop')).length
  current = { ...current, requested_mode: 'AUTO', actual_mode: 'AUTO', mode_pending: false, server_time: new Date(Date.now() + 1).toISOString() }
  await act(async () => FakeRobotSocket.instances[0].frame(current))
  await advance()
  expect(screen.getByRole('button', { name: 'Tiến' })).toBeDisabled()
  expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/stop'))).toHaveLength(before)
  expect(screen.getByText('owned')).toBeInTheDocument()
})

it('stops an active Manual intent once when controls are disabled', async () => {
  await mount()
  fireEvent.pointerDown(screen.getByRole('button', { name: 'Tiến' }))
  await advance()
  const before = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/stop')).length
  current = { ...current, mode_pending: true, server_time: new Date(Date.now() + 1).toISOString() }
  await act(async () => FakeRobotSocket.instances[0].frame(current))
  await advance()
  expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/stop'))).toHaveLength(before + 1)
  fireEvent.pointerUp(screen.getByRole('button', { name: 'Tiến' }))
  await advance()
  expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/stop'))).toHaveLength(before + 1)
})

it('sends stop and keeps the borrow when unmounting', async () => {
  const view = await mount()
  fireEvent.pointerDown(screen.getByRole('button', { name: 'Tiến' }))
  await advance()
  view.unmount()
  await advance()
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/stop'))).toBe(true)
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/release'))).toBe(false)
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/stop'))).toBe(true)
})

it('stops and keeps the borrow after a failed movement request', async () => {
  await mount()
  fetchMock.mockImplementation(async (url) => {
    if (String(url).endsWith('/move')) throw new TypeError('Offline')
    if (String(url).endsWith('/release')) return new Response(null, { status: 204 })
    return json({ command_id: 'stop' })
  })
  fireEvent.pointerDown(screen.getByRole('button', { name: 'Tiến' }))
  await advance()
  expect(screen.getByText('owned')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/release'))).toBe(false)
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/stop'))).toBe(true)
})

it('stops and keeps the borrow when the document becomes hidden', async () => {
  await mount()
  fireEvent.pointerDown(screen.getByRole('button', { name: 'Tiến' }))
  await advance()
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
  fireEvent(document, new Event('visibilitychange'))
  await advance()
  expect(screen.getByText('owned')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/release'))).toBe(false)
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/stop'))).toBe(true)
})

it('stops a late acquisition without returning the borrowed robot', async () => {
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
  resolve(json({ id: 'late', owned: true, expires_at: null, lease_token: 'memory-secret', renew_after_ms: 2000 }))
  await advance()
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/release'))).toBe(false)
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/stop'))).toBe(true)
})

it('restores an existing borrow after reloading without releasing it', async () => {
  current = { ...current, lease: { id: 'lease', owned: true, expires_at: null } }
  await mount(false)
  await advance()
  expect(screen.getByText('owned')).toBeInTheDocument()
  expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/acquire'))).toHaveLength(1)
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/release'))).toBe(false)
})

it('retries a transient renew failure without cancelling Auto or returning the robot', async () => {
  await mount()
  current = { ...current, requested_mode: 'AUTO', actual_mode: 'AUTO', mode_pending: false }
  const previous = fetchMock.getMockImplementation()!
  let renews = 0
  fetchMock.mockImplementation(async (url, init) => {
    if (String(url).endsWith('/renew') && ++renews === 1) throw new TypeError('Offline')
    return previous(url, init)
  })
  for (let i = 0; i < 3; i++) {
    await act(async () => FakeRobotSocket.instances[0].frame({ ...current, server_time: new Date().toISOString() }))
    await advance(2000)
  }
  expect(renews).toBeGreaterThanOrEqual(2)
  expect(screen.getByText('owned')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/release'))).toBe(false)
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/stop'))).toBe(false)
})

it('keeps Auto selected without sending STOP when the window loses focus or hides', async () => {
  await mount()
  current = { ...current, requested_mode: 'AUTO', actual_mode: 'AUTO', mode_pending: false,
    server_time: new Date(Date.now() + 1).toISOString() }
  await act(async () => FakeRobotSocket.instances[0].frame(current))
  fireEvent.blur(window)
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
  fireEvent(document, new Event('visibilitychange'))
  await advance()
  expect(screen.getByText('owned')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/stop'))).toBe(false)
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/release'))).toBe(false)
})
