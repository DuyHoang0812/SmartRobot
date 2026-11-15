import { useEffect, useId, useRef } from 'react'
import type { ReactNode } from 'react'
import { X } from 'lucide-react'

export function Modal({ title, children, onClose, busy = false }: {
  title: string; children: ReactNode; onClose: () => void; busy?: boolean
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const id = useId()
  useEffect(() => {
    const dialog = ref.current
    if (dialog && !dialog.open) dialog.showModal()
  }, [])
  return <dialog ref={ref} aria-labelledby={id} className="admin-modal"
    onCancel={(event) => { event.preventDefault(); if (!busy) onClose() }}>
    <div className="mb-6 flex items-center justify-between gap-4">
      <h2 id={id} className="text-lg font-semibold">{title}</h2>
      <button type="button" className="icon-button" aria-label="Đóng" disabled={busy} onClick={onClose}>
        <X size={20} aria-hidden="true" />
      </button>
    </div>
    {children}
  </dialog>
}
