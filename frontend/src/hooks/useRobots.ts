import { useQuery } from '@tanstack/react-query'
import { useAuth } from './useAuth'
import { ApiError } from '../services/api'
import { robotService } from '../services/robotService'
import type { RobotFiltersValue } from '../types/robots'

export function isRobotNotFound(error: unknown) {
  return error instanceof ApiError && [404, 422].includes(error.status)
}

export function useRobots(page: number, filters: RobotFiltersValue) {
  const { user } = useAuth()
  return useQuery({
    queryKey: ['robots', user?.id, 'list', page, filters],
    queryFn: ({ signal }) => robotService.list(page, filters, signal),
    enabled: Boolean(user?.is_active),
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  })
}

export function useRobot(id: string) {
  const { user } = useAuth()
  return useQuery({
    queryKey: ['robots', user?.id, 'detail', id],
    queryFn: ({ signal }) => robotService.detail(id, signal),
    enabled: Boolean(user?.is_active && id),
    refetchInterval: (query) => isRobotNotFound(query.state.error) ? false : 5000,
    refetchOnWindowFocus: (query) => !isRobotNotFound(query.state.error),
    refetchOnReconnect: (query) => !isRobotNotFound(query.state.error),
    refetchIntervalInBackground: false,
  })
}
