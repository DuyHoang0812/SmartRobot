import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../contexts/auth-context'
import { AppRoutes } from '../routes/AppRoutes'
import type { AdminUser, Robot } from '../types/admin'

const timestamp = '2026-11-15T10:00:00Z'
const admin: AdminUser = { id: 'admin', username: 'administrator', email: 'admin@example.com', role: 'ADMIN', is_active: true, created_at: timestamp, updated_at: timestamp }
const operator: AdminUser = { ...admin, id: 'operator', username: 'operator', email: 'operator@example.com', role: 'USER' }
const robot: Robot = { id: 'robot', name: 'Xe 01', device_id: 'esp32-01', is_active: true, is_simulated: false, status: 'OFFLINE', last_seen_at: null, created_at: timestamp, updated_at: timestamp }
const password = 'valid-test-password'
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status })
let users: AdminUser[] = []
let robots: Robot[] = []
let fetchMock = vi.fn<typeof fetch>()

function mount(path = '/admin/users', role: 'ADMIN' | 'USER' = 'ADMIN') {
  return render(<MemoryRouter initialEntries={[path]}><AuthContext.Provider value={{
    user: { ...admin, role }, loading: false, error: '', login: vi.fn(), logout: vi.fn(), refreshUser: vi.fn().mockResolvedValue(undefined),
  }}><AppRoutes /></AuthContext.Provider></MemoryRouter>)
}

beforeEach(() => {
  users = [{ ...admin }, { ...operator }]
  robots = [{ ...robot }]
  fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const url = new URL(String(input), 'http://localhost')
    const path = url.pathname
    const method = init?.method ?? 'GET'
    const body = init?.body ? JSON.parse(String(init.body)) : {}
    if (path.endsWith('/admin/check')) return json(admin)
    if (method === 'GET' && path.endsWith('/users')) {
      const q = url.searchParams.get('q') ?? ''
      const matches = users.filter((u) => (!q || u.username.includes(q) || u.email.includes(q)) && (!url.searchParams.get('role') || u.role === url.searchParams.get('role')))
      const page = Number(url.searchParams.get('page') ?? 1)
      return json({ items: matches.slice((page - 1) * 20, page * 20), total: matches.length, page, page_size: 20 })
    }
    if (method === 'POST' && path.endsWith('/users')) {
      const next = { ...operator, username: body.username, email: body.email, role: body.role, id: 'new-user' }
      users.push(next)
      return json(next, 201)
    }
    if (path.includes('/users/')) {
      const target = users.find((u) => u.id === path.split('/')[5])
      if (path.endsWith('/reset-password')) return new Response(null, { status: 204 })
      if (target) Object.assign(target, body)
      return json(target)
    }
    if (method === 'GET' && path.endsWith('/robots')) return json({ items: robots, total: robots.length, page: 1, page_size: 20 })
    if (method === 'POST' && path.endsWith('/robots')) {
      const next = { ...robot, ...body, id: 'new-robot' }
      robots.push(next)
      return json({ robot: next, credential: 'one-time-secret-for-new-robot' }, 201)
    }
    if (path.includes('/robots/')) {
      if (path.endsWith('/credentials/rotate')) return json({ robot, credential: 'rotated-secret-once' })
      const target = robots.find((r) => r.id === path.split('/')[5])
      if (target) Object.assign(target, body)
      return json(target)
    }
    return json({ detail: 'Không tìm thấy.' }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
})

describe('Admin management', () => {
  it('renders navigation and the user table with self-disable protected', async () => {
    mount()
    expect(await screen.findByText('operator@example.com')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Người dùng' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Xe robot' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Đăng xuất' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Vô hiệu hóa administrator' })).toBeDisabled()
  })

  it('creates a user through the dialog', async () => {
    mount()
    await screen.findByText('operator@example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Thêm' }))
    const dialog = within(screen.getByRole('dialog'))
    await userEvent.type(dialog.getByLabelText('Username'), 'newuser')
    await userEvent.type(dialog.getByLabelText('Email'), 'newuser@example.com')
    await userEvent.type(dialog.getByLabelText('Mật khẩu mới'), password)
    await userEvent.type(dialog.getByLabelText('Nhập lại mật khẩu'), password)
    await userEvent.click(dialog.getByRole('button', { name: 'Tạo' }))
    expect(await screen.findByText('newuser@example.com')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByText('Đã lưu người dùng.')).toBeInTheDocument()
  })

  it('edits user information', async () => {
    mount()
    await userEvent.click(await screen.findByRole('button', { name: 'Sửa operator' }))
    const dialog = within(screen.getByRole('dialog'))
    await userEvent.clear(dialog.getByLabelText('Email'))
    await userEvent.type(dialog.getByLabelText('Email'), 'edited@example.com')
    await userEvent.click(dialog.getByRole('button', { name: 'Lưu' }))
    expect(await screen.findByText('edited@example.com')).toBeInTheDocument()
  })

  it('changes role using the dedicated endpoint', async () => {
    mount()
    await userEvent.click(await screen.findByRole('button', { name: 'Đổi quyền operator' }))
    const dialog = within(screen.getByRole('dialog'))
    await userEvent.selectOptions(dialog.getByLabelText('Role'), 'ADMIN')
    await userEvent.click(dialog.getByRole('button', { name: 'Lưu' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(fetchMock.mock.calls.some(([url, init]) => String(url).endsWith('/operator/role') && init?.method === 'PATCH')).toBe(true)
  })

  it('confirms disabling and can activate a user again', async () => {
    mount()
    await userEvent.click(await screen.findByRole('button', { name: 'Vô hiệu hóa operator' }))
    expect(screen.getByRole('dialog')).toHaveTextContent('Các phiên đăng nhập')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Lưu' }))
    expect(await screen.findByRole('button', { name: 'Kích hoạt operator' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Kích hoạt operator' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Lưu' }))
    expect(await screen.findByRole('button', { name: 'Vô hiệu hóa operator' })).toBeInTheDocument()
  })

  it('validates password confirmation before resetting it', async () => {
    mount()
    await userEvent.click(await screen.findByRole('button', { name: 'Đặt lại mật khẩu operator' }))
    const dialog = within(screen.getByRole('dialog'))
    expect(dialog.getByLabelText('Mật khẩu mới')).toHaveAttribute('type', 'password')
    await userEvent.type(dialog.getByLabelText('Mật khẩu mới'), password)
    await userEvent.type(dialog.getByLabelText('Nhập lại mật khẩu'), 'different-password')
    await userEvent.click(dialog.getByRole('button', { name: 'Lưu' }))
    expect(dialog.getByRole('alert')).toHaveTextContent('không khớp')
    await userEvent.clear(dialog.getByLabelText('Nhập lại mật khẩu'))
    await userEvent.type(dialog.getByLabelText('Nhập lại mật khẩu'), password)
    await userEvent.click(dialog.getByRole('button', { name: 'Lưu' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/reset-password'))).toBe(true)
  })

  it('searches and filters users', async () => {
    mount()
    await screen.findByText('operator@example.com')
    await userEvent.type(screen.getByRole('searchbox', { name: 'Tìm kiếm' }), 'operator')
    await userEvent.click(screen.getByRole('button', { name: 'Tìm' }))
    await waitFor(() => expect(screen.queryByText('admin@example.com')).not.toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText('Lọc role'), 'ADMIN')
    expect(await screen.findByText('Không có kết quả.')).toBeInTheDocument()
  })

  it('displays mutation errors without closing the dialog', async () => {
    mount()
    await userEvent.click(await screen.findByRole('button', { name: 'Đổi quyền operator' }))
    fetchMock.mockImplementationOnce(async () => json({ detail: 'Không thể hạ quyền Admin cuối cùng.' }, 409))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Lưu' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Admin cuối cùng')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('requests the next page and returns to the previous page', async () => {
    users = Array.from({ length: 21 }, (_, i) => ({ ...operator, id: `user${i}`, username: `user${i}`, email: `user${i}@example.com` }))
    mount()
    expect(await screen.findByText('user0@example.com')).toBeInTheDocument()
    expect(screen.queryByText('user20@example.com')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
    expect(await screen.findByText('user20@example.com')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Trang sau' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Trang trước' }))
    expect(await screen.findByText('user0@example.com')).toBeInTheDocument()
  })

  it('lists robots as Offline with no heartbeat', async () => {
    mount('/admin/robots')
    expect(await screen.findByText('esp32-01')).toBeInTheDocument()
    expect(screen.getByText('Chưa kết nối')).toBeInTheDocument()
    expect(within(screen.getByRole('table')).getByText('Offline')).toBeInTheDocument()
  })

  it('creates a robot, copies the one-time credential and forgets it on close', async () => {
    mount('/admin/robots')
    await screen.findByText('esp32-01')
    await userEvent.click(screen.getByRole('button', { name: 'Thêm' }))
    const dialog = within(screen.getByRole('dialog'))
    await userEvent.type(dialog.getByLabelText('Tên xe'), 'Xe mới')
    await userEvent.type(dialog.getByLabelText('Device ID'), 'esp32-02')
    await userEvent.click(dialog.getByRole('button', { name: 'Tạo' }))
    const secret = await screen.findByLabelText('Credential mới')
    expect(secret).toHaveValue('one-time-secret-for-new-robot')
    const copy = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: copy } })
    fireEvent.click(screen.getByRole('button', { name: 'Sao chép' }))
    expect(await screen.findByText('Đã sao chép.')).toBeInTheDocument()
    expect(copy).toHaveBeenCalledWith('one-time-secret-for-new-robot')
    await userEvent.click(screen.getByRole('button', { name: 'Đã lưu' }))
    expect(screen.queryByLabelText('Credential mới')).not.toBeInTheDocument()
    expect(await screen.findByText('esp32-02')).toBeInTheDocument()
    expect(localStorage.length).toBe(0)
  })

  it('edits a robot', async () => {
    mount('/admin/robots')
    await userEvent.click(await screen.findByRole('button', { name: 'Sửa Xe 01' }))
    const dialog = within(screen.getByRole('dialog'))
    await userEvent.clear(dialog.getByLabelText('Tên xe'))
    await userEvent.type(dialog.getByLabelText('Tên xe'), 'Xe đã sửa')
    await userEvent.click(dialog.getByRole('button', { name: 'Lưu' }))
    expect(await screen.findByText('Xe đã sửa')).toBeInTheDocument()
  })

  it('warns before rotating and displays the new credential once', async () => {
    mount('/admin/robots')
    await userEvent.click(await screen.findByRole('button', { name: 'Xoay credential Xe 01' }))
    expect(screen.getByRole('dialog')).toHaveTextContent('Credential cũ sẽ bị thu hồi ngay')
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/credentials/rotate'))).toBe(false)
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Xoay' }))
    expect(await screen.findByLabelText('Credential mới')).toHaveValue('rotated-secret-once')
    await userEvent.click(screen.getByRole('button', { name: 'Đã lưu' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('disables a robot through confirmation', async () => {
    mount('/admin/robots')
    await userEvent.click(await screen.findByRole('button', { name: 'Vô hiệu hóa Xe 01' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Lưu' }))
    expect(await screen.findByRole('button', { name: 'Kích hoạt Xe 01' })).toBeInTheDocument()
  })

  it('shows loading then an error with a working retry', async () => {
    let finish: (r: Response) => void = () => {}
    fetchMock.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    mount()
    expect(screen.getByRole('status')).toHaveTextContent('Đang tải')
    finish(json({ detail: 'Không thể tải dữ liệu.' }, 503))
    expect(await screen.findByRole('alert')).toHaveTextContent('Không thể tải dữ liệu')
    await userEvent.click(screen.getByRole('button', { name: 'Thử lại' }))
    expect(await screen.findByText('operator@example.com')).toBeInTheDocument()
  })

  it('renders empty robot data', async () => {
    robots = []
    mount('/admin/robots')
    expect(await screen.findByText('Không có kết quả.')).toBeInTheDocument()
  })

  it.each(['/admin/users', '/admin/robots'])('denies USER access to %s', async (path) => {
    mount(path, 'USER')
    expect(await screen.findByRole('heading', { name: 'Không có quyền truy cập' })).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
