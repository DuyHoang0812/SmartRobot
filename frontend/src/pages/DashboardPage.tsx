import { useState } from 'react'
import { useRobots } from '../hooks/useRobots'
import { RobotCard } from '../components/robots/RobotCard'
import { RobotFilters } from '../components/robots/RobotFilters'
import { Feedback } from '../components/admin/Feedback'
import { Pagination } from '../components/admin/ListControls'
import type { RobotFiltersValue } from '../types/robots'

export function DashboardPage() {
  const [page, setPage] = useState(1)
  const [draft, setDraft] = useState('')
  const [filters, setFilters] = useState<RobotFiltersValue>({ q: '', status: '' })
  const robots = useRobots(page, filters)
  function search() { setPage(1); setFilters({ ...filters, q: draft.trim() }) }
  function filter(status: RobotFiltersValue['status']) { setPage(1); setFilters({ ...filters, status }) }
  return <>
    <h1 className="mb-6 text-2xl font-semibold">Xe robot</h1>
    <RobotFilters query={draft} onQueryChange={setDraft} status={filters.status}
      onStatusChange={filter} onSearch={search} onReload={() => { void robots.refetch() }} />
    <Feedback loading={robots.isPending} error={robots.error} empty={robots.data?.items.length === 0}
      emptyMessage="Chưa có xe" errorText="Không thể tải dữ liệu" retry={() => { void robots.refetch() }} />
    {robots.data && !robots.error && <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {robots.data.items.map((robot) => <RobotCard key={robot.id} robot={robot} />)}
      </div>
      <Pagination page={page} total={robots.data.total} size={robots.data.page_size} setPage={setPage} />
    </>}
  </>
}
