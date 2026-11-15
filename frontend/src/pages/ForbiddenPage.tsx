import { Link } from 'react-router-dom'

export function ForbiddenPage() {
  return <>
    <h1 className="mb-3 text-2xl font-semibold">Không có quyền truy cập</h1>
    <Link to="/dashboard" className="text-blue-600 hover:underline">Về tổng quan</Link>
  </>
}
