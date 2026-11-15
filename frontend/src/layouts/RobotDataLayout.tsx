import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

function RobotQueryScope({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 4000 } },
  }))
  // Unmount (including logout) cancels in-flight fetches and removes polling/cache.
  useEffect(() => () => { client.clear() }, [client])
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

export function RobotDataLayout() {
  const { user } = useAuth()
  return <RobotQueryScope key={user?.id}><Outlet /></RobotQueryScope>
}
