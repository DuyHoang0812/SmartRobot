import { beforeEach, expect, it, vi } from 'vitest'
import { apiRequest, login, refreshSession } from '../services/api'
import { beforeLogout, logout } from '../services/api'

const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status })
let fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  document.cookie = 'smartrobot_csrf=test-csrf; Path=/'
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

it('shares a single refresh promise for simultaneous requests', async () => {
  fetchMock.mockImplementation(async () => json({ access_token: 'new-token' }))
  await Promise.all([refreshSession(), refreshSession(), refreshSession()])
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('refreshes once when multiple protected requests receive 401', async () => {
  fetchMock.mockImplementation(async (url, init) => {
    const path = String(url)
    if (path.endsWith('/auth/login')) return json({ access_token: 'old-token' })
    if (path.endsWith('/auth/me')) return json({ username: 'operator' })
    if (path.endsWith('/auth/refresh')) return json({ access_token: 'new-token' })
    return new Headers(init?.headers).get('Authorization') === 'Bearer new-token'
      ? json({ ok: true }) : json({ detail: 'expired' }, 401)
  })
  await login('operator', 'valid-test-password')
  const results = await Promise.all([apiRequest('/protected'), apiRequest('/protected')])
  expect(results).toEqual([{ ok: true }, { ok: true }])
  expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/auth/refresh'))).toHaveLength(1)
})

it('does not refresh a forbidden request', async () => {
  fetchMock.mockImplementation(async () => json({ detail: 'Bạn không có quyền truy cập.' }, 403))
  await expect(apiRequest('/admin/check')).rejects.toThrow('Bạn không có quyền truy cập.')
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('does not send an already aborted request', async () => {
  const controller = new AbortController()
  controller.abort()
  await expect(apiRequest('/robots', { signal: controller.signal })).rejects.toThrow()
  expect(fetchMock).not.toHaveBeenCalled()
})

it('does not refresh authentication after its request was cancelled', async () => {
  const controller = new AbortController()
  fetchMock.mockImplementation(async () => {
    controller.abort()
    return json({ detail: 'expired' }, 401)
  })
  await expect(apiRequest('/robots', { signal: controller.signal })).rejects.toThrow()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('runs control release hooks before revoking authentication', async () => {
  const steps: string[] = []
  const unsubscribe = beforeLogout(async () => { steps.push('release') })
  fetchMock.mockImplementation(async () => { steps.push('logout'); return new Response(null, { status: 204 }) })
  try { await logout() } finally { unsubscribe() }
  expect(steps).toEqual(['release', 'logout'])
})
