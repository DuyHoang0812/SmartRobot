import { useQuery } from '@tanstack/react-query'
import { apiRequest } from '../services/api'
import type { Page } from '../types/admin'

export function useAdminList<T>(resource: 'users' | 'robots', page: number, filters: Record<string, string>) {
  const params = new URLSearchParams({ page: String(page), page_size: '20' })
  Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value) })
  return useQuery({
    queryKey: [`admin-${resource}`, page, filters],
    queryFn: ({ signal }) => apiRequest<Page<T>>(`/admin/${resource}?${params}`, { signal }),
    refetchInterval: resource === 'robots' ? 15000 : false,
  })
}
