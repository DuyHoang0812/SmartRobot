import { useState } from 'react'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../contexts/auth-context'
import { AppRoutes } from '../routes/AppRoutes'
import type { User } from '../types/auth'
import type { UserRobot } from '../types/robots'
import { controlState } from './controlFixtures'

const user: User = { id: 'viewer', username: 'operator', email: 'operator@example.com', role: 'USER', is_active: true }
const online: UserRobot = { id: 'online', name: 'Xe 01', device_id: 'esp32-01', status: 'ONLINE', available: true, is_active: true, last_seen_at: '2026-11-15T10:00:00Z' }
const offline: UserRobot = { ...online, id: 'offline', name: 'Xe 02', device_id: 'esp32-02', status: 'OFFLINE', available: false, last_seen_at: null }
const busy: UserRobot = { ...online, id: 'busy', name: 'Xe 03', device_id: 'esp32-03', status: 'BUSY', available: false }
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status })
let records: UserRobot[] = []
let fetchMock = vi.fn<typeof fetch>()

function Session({ initialUser }: { initialUser: User | null }) {
  const [account, setAccount] = useState(initialUser)
  return <AuthContext.Provider value={{ user: account, loading: false, error: '', login: vi.fn(),
    logout: async () => { setAccount(null) }, refreshUser: vi.fn().mockResolvedValue(undefined) }}>
    <AppRoutes />
  </AuthContext.Provider>
}

function mount(path = '/dashboard', account: User | null = user) {
  return render(<MemoryRouter initialEntries={[path]}><Session initialUser={account} /></MemoryRouter>)
}

beforeEach(() => {
  records = [{ ...online }, { ...offline }, { ...busy }]
  fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input) => {
    const url = new URL(String(input), 'http://localhost')
    const control = records.find((r) => url.pathname === `/api/v1/robots/${r.id}/control/state`)
    if (control) return json(controlState({ robot_id: control.id, status: control.status }))
    if (url.pathname === '/api/v1/robots') {
      const q = url.searchParams.get('q')?.toLowerCase() ?? ''
      const status = url.searchParams.get('status')
      const matches = records.filter((r) => r.name.toLowerCase().includes(q) && (!status || r.status === status))
      const page = Number(url.searchParams.get('page') ?? 1)
      return json({ items: matches.slice((page - 1) * 12, page * 12), total: matches.length, page, page_size: 12 })
    }
    const found = records.find((r) => url.pathname === `/api/v1/robots/${r.id}`)
    return found ? json(found) : json({ detail: 'Xe không tồn tại hoặc đã bị vô hiệu hóa.' }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
})

describe('User Dashboard and robot detail', () => {
  it('renders only real API cards and displays each state', async () => {
    mount()
    expect(screen.getByRole('heading', { name: 'Xe robot' })).toBeInTheDocument()
    const first = await screen.findByRole('article', { name: 'Xe 01' })
    expect(within(first).getByText('Online')).toBeInTheDocument()
    expect(within(screen.getByRole('article', { name: 'Xe 02' })).getByText('Offline')).toBeInTheDocument()
    expect(within(screen.getByRole('article', { name: 'Xe 03' })).getByText('Busy')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /^Xem xe/ })).toHaveLength(3)
    expect(screen.queryByRole('link', { name: 'Quản trị' })).not.toBeInTheDocument()
  })

  it('shows Admin navigation only for ADMIN', async () => {
    mount('/dashboard', { ...user, role: 'ADMIN' })
    await screen.findByRole('article', { name: 'Xe 01' })
    expect(screen.getByRole('link', { name: 'Quản trị' })).toBeInTheDocument()
  })

  it('submits a name search without fetching on every keystroke', async () => {
    mount()
    await screen.findByRole('article', { name: 'Xe 01' })
    await userEvent.type(screen.getByRole('searchbox', { name: 'Tìm kiếm' }), 'Xe 02')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: 'Tìm' }))
    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(1))
    expect(screen.getByRole('article', { name: 'Xe 02' })).toBeInTheDocument()
  })

  it('filters by connection state and can refresh manually', async () => {
    mount()
    await screen.findByRole('article', { name: 'Xe 01' })
    await userEvent.selectOptions(screen.getByLabelText('Trạng thái xe'), 'BUSY')
    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(1))
    expect(screen.getByRole('article', { name: 'Xe 03' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Làm mới' }))
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('status=BUSY'))).toHaveLength(2)
  })

  it('paginates the card grid', async () => {
    records = Array.from({ length: 13 }, (_, i) => ({ ...offline, id: `r${i}`, name: `Robot ${i}` }))
    mount()
    await screen.findByRole('article', { name: 'Robot 0' })
    expect(screen.getAllByRole('article')).toHaveLength(12)
    await userEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
    expect(await screen.findByRole('article', { name: 'Robot 12' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Trang sau' })).toBeDisabled()
  })

  it('shows the exact empty state', async () => {
    records = []
    mount()
    expect(await screen.findByText('Chưa có xe')).toBeInTheDocument()
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
  })

  it('shows loading while the request is pending', async () => {
    fetchMock.mockImplementation(() => new Promise(() => {}))
    mount()
    expect(screen.getByRole('status')).toHaveTextContent('Đang tải')
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
  })

  it('shows network errors with a working retry', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Network failure'))
    mount()
    expect(await screen.findByRole('alert')).toHaveTextContent('Không thể tải dữ liệu')
    await userEvent.click(screen.getByRole('button', { name: 'Thử lại' }))
    expect(await screen.findByRole('article', { name: 'Xe 01' })).toBeInTheDocument()
  })

  it('opens a robot detail and returns to cached dashboard data', async () => {
    mount()
    await userEvent.click(await screen.findByRole('link', { name: 'Xem xe Xe 01' }))
    expect(await screen.findByRole('heading', { name: 'Xe 01' })).toBeInTheDocument()
    expect(screen.getByText('esp32-01')).toBeInTheDocument()
    expect(screen.getByText('Hoạt động')).toBeInTheDocument()
    expect(screen.getByText(/UTC$/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Tiến' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: /Dừng khẩn cấp|^Dừng$/ })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: 'Về Dashboard' }))
    expect(await screen.findByRole('article', { name: 'Xe 01' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([url]) => String(url).startsWith('/api/v1/robots?'))).toHaveLength(1)
  })

  it.each([['offline', 'Xe 02', 'Offline'], ['busy', 'Xe 03', 'Busy']])('allows viewing %s robots', async (id, name, status) => {
    mount(`/robots/${id}`)
    expect(await screen.findByRole('heading', { name })).toBeInTheDocument()
    expect(screen.getByText(status)).toBeInTheDocument()
    if (status === 'Offline') expect(screen.getByText('Chưa kết nối')).toBeInTheDocument()
  })

  it('renders a 404 for a missing or disabled robot', async () => {
    mount('/robots/disabled')
    expect(await screen.findByRole('heading', { name: /Không tìm thấy xe/ })).toBeInTheDocument()
    expect(screen.getByText('Xe không tồn tại hoặc đã bị vô hiệu hóa.')).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Điều khiển Manual' })).not.toBeInTheDocument()
  })

  it('reports detail request errors and retries', async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: 'Unavailable' }, 503))
    mount('/robots/online')
    expect(await screen.findByRole('alert')).toHaveTextContent('Không thể tải dữ liệu')
    await userEvent.click(screen.getByRole('button', { name: 'Thử lại' }))
    expect(await screen.findByRole('heading', { name: 'Xe 01' })).toBeInTheDocument()
  })

  it.each(['/dashboard', '/robots/online'])('protects %s from unauthenticated users', async (path) => {
    mount(path, null)
    expect(await screen.findByRole('button', { name: 'Đăng nhập' })).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('aborts an outstanding dashboard request when logging out', async () => {
    const pending: { signal?: AbortSignal } = {}
    fetchMock.mockImplementation((_url, init) => {
      pending.signal = init?.signal as AbortSignal
      return new Promise(() => {})
    })
    mount()
    await userEvent.click(screen.getByRole('button', { name: 'Đăng xuất' }))
    expect(await screen.findByRole('button', { name: 'Đăng nhập' })).toBeInTheDocument()
    expect(pending.signal?.aborted).toBe(true)
  })
})
