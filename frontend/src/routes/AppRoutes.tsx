import { Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from './ProtectedRoute'
import { AdminRoute } from './AdminRoute'
import { LoginPage } from '../pages/LoginPage'
import { DashboardPage } from '../pages/DashboardPage'
import { AdminPage } from '../pages/AdminPage'
import { ForbiddenPage } from '../pages/ForbiddenPage'
import { AppLayout } from '../layouts/AppLayout'
import { AdminLayout } from '../layouts/AdminLayout'
import { UsersPage } from '../pages/admin/UsersPage'
import { RobotsPage } from '../pages/admin/RobotsPage'
import { RobotControlPage } from '../pages/RobotControlPage'
import { RobotDataLayout } from '../layouts/RobotDataLayout'

export function AppRoutes() {
  return <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route element={<ProtectedRoute />}>
      <Route element={<AppLayout />}>
        <Route element={<RobotDataLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/robots/:id" element={<RobotControlPage />} />
        </Route>
        <Route path="/403" element={<ForbiddenPage />} />
        <Route element={<AdminRoute />}>
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<AdminPage />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="robots" element={<RobotsPage />} />
          </Route>
        </Route>
      </Route>
    </Route>
    <Route path="*" element={<Navigate to="/dashboard" replace />} />
  </Routes>
}
