import { useEffect, useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Bot, Users } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'

export function AdminLayout() {
  const [client] = useState(() => new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 5000, refetchOnWindowFocus: false } },
  }))
  useEffect(() => () => { client.clear() }, [client])
  return <QueryClientProvider client={client}>
    <div className="flex flex-col gap-6 md:flex-row md:gap-8">
      <nav aria-label="Quản trị" className="flex shrink-0 gap-2 md:w-44 md:flex-col">
        <NavLink to="/admin/users" className="nav-link"><Users size={18} aria-hidden="true" />Người dùng</NavLink>
        <NavLink to="/admin/robots" className="nav-link"><Bot size={18} aria-hidden="true" />Xe robot</NavLink>
      </nav>
      <section className="min-w-0 flex-1"><Outlet /></section>
    </div>
  </QueryClientProvider>
}
