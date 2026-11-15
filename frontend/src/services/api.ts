import type { TokenResponse, User } from '../types/auth'

// Access tokens exist only in this module's memory. Cookies are handled by the browser.
let accessToken: string | null = null
let generation = 0
let refreshPromise: Promise<void> | null = null
const expiredListeners = new Set<() => void>()
const logoutListeners = new Set<() => Promise<void>>()
const API_BASE = '/api/v1'

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export function onSessionExpired(listener: () => void) {
  expiredListeners.add(listener)
  return () => { expiredListeners.delete(listener) }
}

export function beforeLogout(listener: () => Promise<void>) {
  logoutListeners.add(listener)
  return () => { logoutListeners.delete(listener) }
}

export function clearSession() {
  generation += 1
  accessToken = null
  expiredListeners.forEach((listener) => listener())
}

function csrfToken(): string {
  return document.cookie.split('; ').find((cookie) => cookie.startsWith('smartrobot_csrf='))
    ?.split('=').slice(1).join('=') ?? ''
}

async function authLock<T>(action: () => Promise<T>): Promise<T> {
  // Serialize cookie rotation across tabs where Web Locks are available.
  if (navigator.locks) return navigator.locks.request('smartrobot-auth', action)
  return action()
}

async function checked(response: Response): Promise<Response> {
  if (response.ok) return response
  const body = await response.json().catch(() => null)
  const message = typeof body?.detail === 'string' ? body.detail :
    response.status === 422 ? 'Thông tin không hợp lệ.' : 'Không thể thực hiện yêu cầu.'
  throw new ApiError(response.status, message)
}

function send(path: string, init: RequestInit = {}, token: string | null = null) {
  const headers = new Headers(init.headers)
  if (init.body) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  return fetch(`${API_BASE}${path}`, { ...init, headers, credentials: 'include', cache: 'no-store' })
}

export function refreshSession(): Promise<void> {
  if (refreshPromise) return refreshPromise
  const started = generation
  refreshPromise = authLock(async () => {
    if (started !== generation) throw new ApiError(401, 'Phiên đăng nhập đã thay đổi.')
    const csrf = csrfToken()
    if (!csrf) throw new ApiError(401, 'Vui lòng đăng nhập.')
    const response = await checked(await send('/auth/refresh', {
      method: 'POST', headers: { 'X-CSRF-Token': csrf },
    }))
    const data: TokenResponse = await response.json()
    if (started !== generation) throw new ApiError(401, 'Phiên đăng nhập đã thay đổi.')
    accessToken = data.access_token
  }).catch((error: unknown) => {
    if (started === generation && error instanceof ApiError && [401, 403].includes(error.status)) {
      clearSession()
    }
    throw error
  }).finally(() => { refreshPromise = null })
  return refreshPromise
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  init.signal?.throwIfAborted()
  const original = accessToken
  let response = await send(path, init, original)
  init.signal?.throwIfAborted()
  if (response.status === 401) {
    // A parallel request may already have refreshed this token.
    if (!accessToken || accessToken === original) await refreshSession()
    init.signal?.throwIfAborted()
    response = await send(path, init, accessToken)
  }
  try {
    await checked(response)
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) clearSession()
    throw error
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}

export const getMe = () => apiRequest<User>('/auth/me')

export async function socketAccessToken(): Promise<string> {
  if (!accessToken) await refreshSession()
  if (!accessToken) throw new ApiError(401, 'Vui lòng đăng nhập.')
  return accessToken
}

export async function login(identifier: string, password: string): Promise<User> {
  const started = ++generation
  await authLock(async () => {
    const response = await checked(await send('/auth/login', {
      method: 'POST', body: JSON.stringify({ identifier, password }),
    }))
    const data: TokenResponse = await response.json()
    if (started !== generation) throw new ApiError(401, 'Phiên đăng nhập đã thay đổi.')
    accessToken = data.access_token
  })
  return getMe()
}

export async function logout(): Promise<void> {
  await Promise.allSettled([...logoutListeners].map((listener) => listener()))
  generation += 1
  await authLock(async () => {
    await checked(await send('/auth/logout', {
      method: 'POST', headers: { 'X-CSRF-Token': csrfToken() },
    }))
    clearSession()
  })
}

export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Không thể kết nối. Vui lòng thử lại.'
}
