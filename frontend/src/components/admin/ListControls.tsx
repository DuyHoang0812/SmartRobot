import type { FormEvent, ReactNode } from 'react'
import { ChevronLeft, ChevronRight, RefreshCw, Search } from 'lucide-react'

export function ListControls({ query, setQuery, onSearch, onReload, children, maxLength = 254 }: {
  query: string; setQuery: (q: string) => void; onSearch: () => void;
  onReload: () => void; children: ReactNode; maxLength?: number
}) {
  function submit(event: FormEvent) { event.preventDefault(); onSearch() }
  return <div className="mb-5 flex flex-wrap items-center gap-3">
    <form onSubmit={submit} role="search" className="flex min-w-0 flex-1 gap-2 sm:max-w-sm">
      <label className="sr-only" htmlFor="admin-search">Tìm kiếm</label>
      <input id="admin-search" className="field-input h-10 min-w-0" type="search" value={query}
        maxLength={maxLength} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm kiếm" />
      <button className="secondary-button" type="submit" aria-label="Tìm"><Search size={18} aria-hidden="true" /></button>
    </form>
    {children}
    <button type="button" className="icon-button" aria-label="Làm mới" onClick={onReload}><RefreshCw size={18} aria-hidden="true" /></button>
  </div>
}

export function Pagination({ page, total, size = 20, setPage }: {
  page: number; total: number; size?: number; setPage: (page: number) => void
}) {
  const pages = Math.max(1, Math.ceil(total / size))
  return <nav aria-label="Phân trang" className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-slate-500">
    <span>{total} kết quả</span>
    <div className="flex items-center gap-3">
      <button className="icon-button" aria-label="Trang trước" disabled={page <= 1} onClick={() => setPage(Math.min(page - 1, pages))}><ChevronLeft size={18} aria-hidden="true" /></button>
      <span>{page > pages ? `Trang ${page}` : `Trang ${page}/${pages}`}</span>
      <button className="icon-button" aria-label="Trang sau" disabled={page >= pages} onClick={() => setPage(page + 1)}><ChevronRight size={18} aria-hidden="true" /></button>
    </div>
  </nav>
}

export function ActiveFilter({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return <select aria-label="Trạng thái kích hoạt" className="filter-select" value={value} onChange={(event) => onChange(event.target.value)}>
    <option value="">Mọi trạng thái</option><option value="true">Hoạt động</option><option value="false">Vô hiệu hóa</option>
  </select>
}
