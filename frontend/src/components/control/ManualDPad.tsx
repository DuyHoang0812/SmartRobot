import { useEffect, useRef, useState } from 'react'
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp } from 'lucide-react'
import type { MoveDirection } from '../../types/control'

const keys: Record<string, MoveDirection> = { w: 'FORWARD', arrowup: 'FORWARD', s: 'BACKWARD', arrowdown: 'BACKWARD',
  a: 'TURN_LEFT', arrowleft: 'TURN_LEFT', d: 'TURN_RIGHT', arrowright: 'TURN_RIGHT' }
const buttons = [
  { direction: 'FORWARD', label: 'Tiến', icon: ArrowUp, position: 'col-start-2 row-start-1' },
  { direction: 'TURN_LEFT', label: 'Quay trái', icon: ArrowLeft, position: 'col-start-1 row-start-2' },
  { direction: 'TURN_RIGHT', label: 'Quay phải', icon: ArrowRight, position: 'col-start-3 row-start-2' },
  { direction: 'BACKWARD', label: 'Lùi', icon: ArrowDown, position: 'col-start-2 row-start-3' },
] as const

export function ManualDPad({ disabled, onStart, onStop }: {
  disabled: boolean; onStart: (direction: MoveDirection) => void; onStop: () => void
}) {
  const [pressed, setPressed] = useState<MoveDirection | null>(null)
  const active = useRef<MoveDirection | null>(null)
  const source = useRef<'pointer' | string | null>(null)
  const callbacks = useRef({ onStart, onStop })
  useEffect(() => { callbacks.current = { onStart, onStop } }, [onStart, onStop])
  useEffect(() => {
    function finish() {
      if (active.current) callbacks.current.onStop()
      active.current = null; source.current = null; setPressed(null)
    }
    function down(event: KeyboardEvent) {
      const target = event.target
      if (disabled || event.repeat || (target instanceof Element && target.closest('input, textarea, select, [contenteditable="true"]'))) return
      const direction = keys[event.key.toLowerCase()]
      if (!direction) return
      event.preventDefault()
      if (active.current === direction) return
      if (active.current) callbacks.current.onStop()
      active.current = direction; source.current = event.key.toLowerCase(); setPressed(direction)
      callbacks.current.onStart(direction)
    }
    function up(event: KeyboardEvent) {
      if (source.current === event.key.toLowerCase()) { event.preventDefault(); finish() }
    }
    function hidden() { if (document.hidden) finish() }
    window.addEventListener('keydown', down); window.addEventListener('keyup', up)
    window.addEventListener('blur', finish); document.addEventListener('visibilitychange', hidden)
    return () => {
      if (active.current) callbacks.current.onStop()
      active.current = null; source.current = null
      window.removeEventListener('keydown', down); window.removeEventListener('keyup', up)
      window.removeEventListener('blur', finish); document.removeEventListener('visibilitychange', hidden)
    }
  }, [disabled])
  function end() {
    if (active.current) onStop()
    active.current = null; source.current = null; setPressed(null)
  }
  return <div className="mx-auto grid max-w-sm grid-cols-3 grid-rows-3 gap-2" role="group" aria-label="Điều khiển Manual">
    {buttons.map(({ direction, label, icon: Icon, position }) => <button key={direction}
      type="button" disabled={disabled} aria-pressed={!disabled && pressed === direction}
      className={`${position} flex min-h-20 touch-none select-none flex-col items-center justify-center gap-2 rounded-xl border border-slate-200 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-40 ${!disabled && pressed === direction ? 'bg-blue-600 text-white' : 'bg-slate-50 text-slate-700'}`}
      onContextMenu={(event) => event.preventDefault()}
      onPointerDown={(event) => {
        if (disabled || (event.pointerType === 'mouse' && event.button !== 0)) return
        event.preventDefault()
        event.currentTarget.setPointerCapture?.(event.pointerId)
        if (active.current) onStop()
        active.current = direction; source.current = 'pointer'; setPressed(direction); onStart(direction)
      }}
      onPointerUp={end} onPointerCancel={end} onLostPointerCapture={end}>
      <Icon size={23} aria-hidden="true" />{label}
    </button>)}
  </div>
}
