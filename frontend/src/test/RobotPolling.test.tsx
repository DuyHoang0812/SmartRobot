import { act, cleanup, render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider, focusManager } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { AuthContext } from '../contexts/auth-context'
import { useRobot, useRobots } from '../hooks/useRobots'
import type { UserRobot } from '../types/robots'

const robot: UserRobot = { id: 'r1', name: 'Xe polling', device_id: 'esp32', status: 'ONLINE', available: true, is_active: true, last_seen_at: '2026-11-15T10:00:00Z' }
const clients: QueryClient[] = []
let current = { ...robot }
let fetchMock = vi.fn<typeof fetch>()
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status })

function ListProbe() {
  const result = useRobots(1, { q: '', status: '' })
  return <span>{result.data?.items[0]?.status ?? 'pending'}</span>
}

function DetailProbe() {
  const result = useRobot('r1')
  return <span>{result.error ? 'error' : result.data?.status ?? 'pending'}</span>
}

function mount(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 4000 } } })
  clients.push(client)
  return render(<AuthContext.Provider value={{ user: { id: 'viewer', username: 'operator', email: 'u@example.com', role: 'USER', is_active: true }, loading: false, error: '', login: vi.fn(), logout: vi.fn(), refreshUser: vi.fn() }}>
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  </AuthContext.Provider>)
}

async function advance(ms = 20) {
  await act(async () => { await vi.advanceTimersByTimeAsync(ms) })
}

beforeEach(() => {
  vi.useFakeTimers()
  focusManager.setFocused(true)
  current = { ...robot }
  fetchMock = vi.fn<typeof fetch>().mockImplementation(async (url) => String(url).includes('?')
    ? json({ items: [current], total: 1, page: 1, page_size: 12 }) : json(current))
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  cleanup()
  clients.splice(0).forEach((client) => client.clear())
  focusManager.setFocused(undefined)
  vi.useRealTimers()
})

it('refreshes the list after five seconds and stops after unmount', async () => {
  const view = mount(<ListProbe />)
  await advance()
  expect(screen.getByText('ONLINE')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
  current = { ...robot, status: 'OFFLINE', available: false }
  await advance(5000)
  expect(screen.getByText('OFFLINE')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(2)
  view.unmount()
  await advance(10000)
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

it('refreshes robot detail and removes polling on unmount', async () => {
  const view = mount(<DetailProbe />)
  await advance()
  current = { ...robot, status: 'BUSY', available: false }
  await advance(5000)
  expect(screen.getByText('BUSY')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(2)
  view.unmount()
  await advance(10000)
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

it('shares one list request between concurrent observers', async () => {
  mount(<><ListProbe /><ListProbe /></>)
  await advance()
  expect(screen.getAllByText('ONLINE')).toHaveLength(2)
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('aborts an in-flight poll when the observer unmounts', async () => {
  const view = mount(<ListProbe />)
  await advance()
  const pending: { signal?: AbortSignal } = {}
  fetchMock.mockImplementation((_url, init) => {
    pending.signal = init?.signal as AbortSignal
    return new Promise(() => {})
  })
  await advance(5000)
  expect(pending.signal?.aborted).toBe(false)
  view.unmount()
  expect(pending.signal?.aborted).toBe(true)
  await advance(10000)
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

it('stops polling detail once the robot is disabled or missing', async () => {
  mount(<DetailProbe />)
  await advance()
  fetchMock.mockImplementation(async () => json({ detail: 'Not found' }, 404))
  await advance(5000)
  expect(screen.getByText('error')).toBeInTheDocument()
  await advance(15000)
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

it('pauses polling while the page is not focused', async () => {
  mount(<ListProbe />)
  await advance()
  focusManager.setFocused(false)
  await advance(10000)
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('recovers from a network error on the next interval', async () => {
  fetchMock.mockRejectedValueOnce(new TypeError('Network failure'))
  mount(<ListProbe />)
  await advance()
  expect(fetchMock).toHaveBeenCalledTimes(1)
  await advance(5000)
  expect(screen.getByText('ONLINE')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(2)
})
