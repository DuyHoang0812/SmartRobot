import { LoaderCircle } from 'lucide-react'
import { errorMessage } from '../../services/api'

export function Feedback({ loading, error, empty, retry, emptyMessage = 'Không có kết quả.', errorText }: {
  loading: boolean; error: unknown; empty: boolean; retry: () => void;
  emptyMessage?: string; errorText?: string
}) {
  if (loading) return <p role="status" className="list-state"><LoaderCircle size={19} className="animate-spin" aria-hidden="true" />Đang tải…</p>
  if (error) return <div role="alert" className="list-state text-red-700">{errorText ?? errorMessage(error)}<button className="secondary-button" onClick={retry}>Thử lại</button></div>
  if (empty) return <p className="list-state">{emptyMessage}</p>
  return null
}
