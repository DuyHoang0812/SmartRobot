import { ListControls } from '../admin/ListControls'
import type { RobotFiltersValue } from '../../types/robots'

export function RobotFilters({ query, onQueryChange, status, onStatusChange, onSearch, onReload }: {
  query: string; onQueryChange: (q: string) => void; status: RobotFiltersValue['status'];
  onStatusChange: (status: RobotFiltersValue['status']) => void;
  onSearch: () => void; onReload: () => void
}) {
  return <ListControls query={query} setQuery={onQueryChange} onSearch={onSearch} onReload={onReload} maxLength={120}>
    <select aria-label="Trạng thái xe" className="filter-select" value={status}
      onChange={(event) => onStatusChange(event.target.value as RobotFiltersValue['status'])}>
      <option value="">Mọi trạng thái</option><option value="ONLINE">Online</option>
      <option value="OFFLINE">Offline</option><option value="BUSY">Busy</option>
    </select>
  </ListControls>
}
