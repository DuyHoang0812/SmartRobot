import { LoaderCircle } from 'lucide-react'

export function Loading() {
  return <div role="status" className="flex min-h-screen items-center justify-center gap-2 text-slate-500">
    <LoaderCircle className="animate-spin" size={20} aria-hidden="true" />
    Đang tải…
  </div>
}
