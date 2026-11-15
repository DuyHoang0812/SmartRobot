import { apiRequest } from './api'
import type { Page } from '../types/admin'
import type { RobotFiltersValue, UserRobot } from '../types/robots'

export const robotService = {
  list(page: number, filters: RobotFiltersValue, signal?: AbortSignal) {
    const params = new URLSearchParams({ page: String(page), page_size: '12' })
    if (filters.q) params.set('q', filters.q)
    if (filters.status) params.set('status', filters.status)
    return apiRequest<Page<UserRobot>>(`/robots?${params}`, { signal })
  },
  detail(id: string, signal?: AbortSignal) {
    return apiRequest<UserRobot>(`/robots/${encodeURIComponent(id)}`, { signal })
  },
}
