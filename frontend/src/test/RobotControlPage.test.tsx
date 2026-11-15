import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { AuthContext } from '../contexts/auth-context'
import { AppRoutes } from '../routes/AppRoutes'
import * as api from '../services/api'
import { controlState, FakeRobotSocket } from './controlFixtures'
import type { ControlState } from '../types/control'

let current: ControlState
let fetchMock = vi.fn<typeof fetch>()
const expires = () => new Date(Date.now() + 10000).toISOString()
const json = (value: unknown) => new Response(JSON.stringify(value), { status: 200 })

beforeEach(() => {
  current = controlState({ actual_mode: 'MANUAL', mode_pending: false, telemetry_fresh: true, actual_movement: 'STOP' })
  FakeRobotSocket.instances = []
  vi.stubGlobal('WebSocket', FakeRobotSocket)
  vi.spyOn(api, 'socketAccessToken').mockResolvedValue('memory-token')
  fetchMock = vi.fn<typeof fetch>().mockImplementation(async (url, init) => {
    const path = String(url)
    if (path.endsWith('/control/state')) return json({ ...current, server_time: new Date().toISOString() })
    if (path.endsWith('/acquire')) {
      current = { ...current, lease: { id: 'lease', owned: true, expires_at: expires() } }
      return json({ ...current.lease, lease_token: 'secret-memory-only', renew_after_ms: 2000 })
    }
    if (path.endsWith('/renew')) return json({ ...current.lease, expires_at: expires() })
    if (path.endsWith('/release')) {
      current = { ...current, lease: { id: null, owned: false, expires_at: null } }
      return new Response(null, { status: 204 })
    }
    if (path.endsWith('/mode')) {
      current = { ...current, requested_mode: JSON.parse(String(init?.body)).mode, mode_pending: true }
      return json({ command_id: 'mode', status: 'ACCEPTED' })
    }
    if (path.endsWith('/stop') || path.endsWith('/move')) return json({ command_id: 'accepted', status: 'ACCEPTED' })
    return json({ id: 'online', name: 'Xe điều khiển', device_id: 'esp32', is_active: true,
      status: current.status, available: current.status === 'ONLINE', last_seen_at: null })
  })
  vi.stubGlobal('fetch', fetchMock)
})

async function mount() {
  const view = render(<MemoryRouter initialEntries={['/robots/online']}><AuthContext.Provider value={{
    user: { id: 'viewer', username: 'operator', email: 'u@example.com', role: 'USER', is_active: true },
    loading: false, error: '', login: vi.fn(), logout: vi.fn(), refreshUser: vi.fn(),
  }}><AppRoutes /></AuthContext.Provider></MemoryRouter>)
  await screen.findByRole('heading', { name: 'Xe điều khiển' })
  await waitFor(() => expect(FakeRobotSocket.instances).toHaveLength(1))
  await act(async () => { FakeRobotSocket.instances[0].open(); FakeRobotSocket.instances[0].frame(current) })
  return view
}

async function own() {
  await userEvent.click(screen.getByRole('button', { name: 'Nhận điều khiển' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Tiến' })).toBeEnabled())
}

it('renders four disabled directions until a valid lease is acquired', async () => {
  await mount()
  expect(screen.getByRole('button', { name: 'Tiến' })).toBeDisabled()
  expect(within(screen.getByRole('group', { name: 'Điều khiển Manual' })).getAllByRole('button')).toHaveLength(4)
  expect(screen.queryByRole('button', { name: /Dừng khẩn cấp|^Dừng$/ })).not.toBeInTheDocument()
  await own()
  expect(screen.getByRole('button', { name: 'Thoát điều khiển' })).toBeEnabled()
})

it('does not claim actual movement from an accepted move', async () => {
  await mount(); await own()
  fireEvent.keyDown(window, { key: 'w' })
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/move'))).toBe(true))
  expect(screen.getByText('Đã dừng')).toBeInTheDocument()
  expect(await screen.findByText('Đã nhận yêu cầu')).toBeInTheDocument()
  fireEvent.keyUp(window, { key: 'w' })
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/stop'))).toBe(true))
})

it('requests Auto and keeps controls disabled while waiting for the device', async () => {
  await mount(); await own()
  await userEvent.click(screen.getByRole('button', { name: 'Auto' }))
  expect(await screen.findByText('Chờ thiết bị')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Tiến' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Manual' })).toBeDisabled()
})

it('releases control explicitly', async () => {
  await mount(); await own()
  await userEvent.click(screen.getByRole('button', { name: 'Thoát điều khiển' }))
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/release'))).toBe(true))
  expect(screen.getByRole('button', { name: 'Tiến' })).toBeDisabled()
})

it.each(['OFFLINE', 'BUSY'] as const)('disables controls when robot is %s', async (status) => {
  current = { ...current, status, lease: status === 'BUSY' ? { id: null, owned: false, expires_at: expires() } : current.lease }
  await mount()
  expect(screen.getByRole('button', { name: 'Tiến' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Nhận điều khiển' })).toBeDisabled()
})

it('shows only device-provided obstacle and sensor data', async () => {
  current = { ...current, obstacle: 'BLOCKED', distance_cm: 10, buzzer: true }
  await mount()
  expect(screen.getByText('Có vật cản')).toBeInTheDocument()
  expect(screen.getByText('10 cm')).toBeInTheDocument()
  expect(screen.getByText('Bật')).toBeInTheDocument()
  await act(async () => FakeRobotSocket.instances[0].frame({ ...current, obstacle: 'SENSOR_ERROR', distance_cm: null, server_time: new Date().toISOString() }))
  expect(await screen.findByText('Lỗi cảm biến')).toBeInTheDocument()
})

it('stops and releases when the WebSocket disconnects', async () => {
  await mount(); await own()
  fireEvent.keyDown(window, { key: 'w' })
  await act(async () => FakeRobotSocket.instances[0].disconnect())
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/release'))).toBe(true))
  expect(screen.getByRole('button', { name: 'Tiến' })).toBeDisabled()
})

it('stops and releases on blur and component unmount', async () => {
  const view = await mount(); await own()
  fireEvent.keyDown(window, { key: 'w' })
  fireEvent.blur(window)
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/release'))).toBe(true))
  view.unmount()
})

it('shows device acknowledgement from WebSocket and clears live claims on disconnect', async () => {
  await mount()
  await act(async () => FakeRobotSocket.instances[0].frame({ ...current, sequence: 2,
    acknowledgement: { sequence: 2, status: 'APPLIED', acknowledged_at: new Date().toISOString() },
    server_time: new Date().toISOString() }))
  expect(await screen.findByText('Đã áp dụng yêu cầu')).toBeInTheDocument()
  expect(screen.getByText('Đã dừng')).toBeInTheDocument()
  await act(async () => FakeRobotSocket.instances[0].disconnect())
  expect(screen.queryByText('Đã áp dụng yêu cầu')).not.toBeInTheDocument()
  expect(screen.queryByText('Đã dừng')).not.toBeInTheDocument()
})
