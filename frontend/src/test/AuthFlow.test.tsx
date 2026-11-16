import { StrictMode } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../contexts/AuthProvider'
import { AppRoutes } from '../routes/AppRoutes'
import { apiRequest } from '../services/api'
import type { User } from '../types/auth'

const user: User = { id: 'user-id', username: 'operator', email: 'operator@example.test', role: 'USER', is_active: true }
const password = 'valid-test-password'
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
let currentUser = user
let fetchMock = vi.fn<typeof fetch>()

function mount(path = '/login', strict = false) {
  const app = <MemoryRouter initialEntries={[path]}><AuthProvider><AppRoutes /></AuthProvider></MemoryRouter>
  return render(strict ? <StrictMode>{app}</StrictMode> : app)
}

async function fillLogin() {
  const input = userEvent.setup()
  await input.type(await screen.findByLabelText('Username hoặc Email'), 'operator')
  await input.type(screen.getByLabelText('Mật khẩu'), password)
  await input.click(screen.getByRole('button', { name: 'Đăng nhập' }))
}

beforeEach(() => {
  currentUser = user
  fetchMock = vi.fn<typeof fetch>().mockImplementation(async (url) => {
    const path = String(url)
    if (path.endsWith('/auth/me') || path.endsWith('/admin/check')) return json(currentUser)
    if (path.startsWith('/api/v1/robots?')) return json({ items: [], total: 0, page: 1, page_size: 12 })
    if (path.endsWith('/auth/logout')) return new Response(null, { status: 204 })
    return json({ access_token: 'memory-token', token_type: 'bearer', expires_in: 900 })
  })
  vi.stubGlobal('fetch', fetchMock)
})

describe('Authentication UI', () => {
  it('renders the Vietnamese login form and password toggle', async () => {
    mount()
    expect(await screen.findByRole('heading', { name: 'SmartRobot' })).toBeInTheDocument()
    const field = screen.getByLabelText('Mật khẩu')
    expect(field).toHaveAttribute('type', 'password')
    await userEvent.click(screen.getByRole('button', { name: 'Hiện mật khẩu' }))
    expect(field).toHaveAttribute('type', 'text')
    await userEvent.click(screen.getByRole('button', { name: 'Ẩn mật khẩu' }))
    expect(field).toHaveAttribute('type', 'password')
  })

  it('validates empty identity and short password before sending a request', async () => {
    mount()
    await userEvent.click(await screen.findByRole('button', { name: 'Đăng nhập' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Vui lòng nhập tài khoản.')
    await userEvent.type(screen.getByLabelText('Username hoặc Email'), 'operator')
    await userEvent.type(screen.getByLabelText('Mật khẩu'), 'short')
    await userEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    expect(screen.getByRole('alert')).toHaveTextContent('12 đến 128')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('logs in, fetches the current user and navigates to dashboard', async () => {
    mount()
    await fillLogin()
    expect(await screen.findByRole('heading', { name: 'Xe robot' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Quản trị' })).not.toBeInTheDocument()
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
    const request = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/auth/me'))
    expect(new Headers(request?.[1]?.headers).get('Authorization')).toBe('Bearer memory-token')
  })

  it('shows a generic login failure', async () => {
    fetchMock.mockResolvedValue(json({ detail: 'Tài khoản hoặc mật khẩu không đúng.' }, 401))
    mount()
    await fillLogin()
    expect(await screen.findByRole('alert')).toHaveTextContent('Tài khoản hoặc mật khẩu không đúng.')
    expect(screen.getByRole('button', { name: 'Đăng nhập' })).toBeEnabled()
  })

  it('redirects unauthenticated protected routes to login', async () => {
    mount('/dashboard')
    expect(await screen.findByRole('button', { name: 'Đăng nhập' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Xe robot' })).not.toBeInTheDocument()
  })

  it('restores a session from the refresh cookie and redirects login', async () => {
    document.cookie = 'smartrobot_csrf=test-csrf; Path=/'
    mount('/login')
    expect(await screen.findByRole('heading', { name: 'Xe robot' })).toBeInTheDocument()
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/auth/refresh'))
    expect(new Headers(call?.[1]?.headers).get('X-CSRF-Token')).toBe('test-csrf')
    expect(call?.[1]?.credentials).toBe('include')
  })

  it('shows 403 to USER entering the admin route', async () => {
    document.cookie = 'smartrobot_csrf=test-csrf; Path=/'
    mount('/admin')
    expect(await screen.findByRole('heading', { name: 'Không có quyền truy cập' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/admin/check'))).toBe(false)
  })

  it('allows ADMIN and checks its permission at the backend', async () => {
    currentUser = { ...user, role: 'ADMIN' }
    document.cookie = 'smartrobot_csrf=test-csrf; Path=/'
    mount('/admin')
    expect(await screen.findByText('Quyền quản trị đã được xác nhận.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Quản trị' })).toBeInTheDocument()
  })

  it('logs out through the API and returns to login', async () => {
    document.cookie = 'smartrobot_csrf=test-csrf; Path=/'
    mount('/dashboard')
    await userEvent.click(await screen.findByRole('button', { name: 'Đăng xuất' }))
    expect(await screen.findByRole('button', { name: 'Đăng nhập' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/auth/logout'))).toBe(true)
  })

  it('keeps the page and reports a failed logout', async () => {
    document.cookie = 'smartrobot_csrf=test-csrf; Path=/'
    mount('/dashboard')
    const button = await screen.findByRole('button', { name: 'Đăng xuất' })
    fetchMock.mockRejectedValue(new TypeError('Network failure'))
    await userEvent.click(button)
    // Robot polling may also fail; target the logout error instead of assuming a single alert.
    expect(await screen.findByText('Không thể kết nối. Vui lòng thử lại.')).toHaveAttribute('role', 'alert')
    expect(screen.getByRole('heading', { name: 'Xe robot' })).toBeInTheDocument()
  })

  it('returns to login when the restored session is expired', async () => {
    document.cookie = 'smartrobot_csrf=expired; Path=/'
    fetchMock.mockResolvedValue(json({ detail: 'Phiên đăng nhập đã hết hạn.' }, 401))
    mount('/dashboard')
    expect(await screen.findByRole('button', { name: 'Đăng nhập' })).toBeInTheDocument()
  })

  it('deduplicates restoration under React StrictMode', async () => {
    document.cookie = 'smartrobot_csrf=test-csrf; Path=/'
    mount('/dashboard', true)
    expect(await screen.findByRole('heading', { name: 'Xe robot' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/auth/refresh'))).toHaveLength(1)
  })

  it('redirects an active page after refresh authentication fails', async () => {
    document.cookie = 'smartrobot_csrf=test-csrf; Path=/'
    mount('/dashboard')
    await screen.findByRole('heading', { name: 'Xe robot' })
    fetchMock.mockImplementation(async () => json({ detail: 'Phiên đăng nhập đã hết hạn.' }, 401))
    // Trigger the same protected API path used by future pages.
    await expect(apiRequest('/auth/me')).rejects.toThrow('Phiên đăng nhập đã hết hạn.')
    expect(await screen.findByRole('button', { name: 'Đăng nhập' })).toBeInTheDocument()
  })

  it('shows a loading state during login', async () => {
    mount()
    const form = await screen.findByRole('form', { name: 'Đăng nhập' })
    fireEvent.change(screen.getByLabelText('Username hoặc Email'), { target: { value: 'operator' } })
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: password } })
    let finish: (response: Response) => void = () => {}
    fetchMock.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    fireEvent.submit(form)
    expect(screen.getByRole('button', { name: 'Đang đăng nhập…' })).toBeDisabled()
    finish(json({ access_token: 'memory-token' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Xe robot' })).toBeInTheDocument())
  })
})
