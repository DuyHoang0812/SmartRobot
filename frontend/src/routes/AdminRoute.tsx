import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { Loading } from '../components/Loading'

export function AdminRoute() {
  const { user, loading } = useAuth()
  if (loading) return <Loading />
  if (!user) return <Navigate to="/login" replace />
  return user.role === 'ADMIN' ? <Outlet /> : <Navigate to="/403" replace />
}
