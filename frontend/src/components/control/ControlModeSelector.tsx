import type { Mode } from '../../types/control'

export function ControlModeSelector({ mode, disabled, onChange }: {
  mode: Mode; disabled: boolean; onChange: (mode: Mode) => void
}) {
  return <div role="group" aria-label="Chế độ điều khiển" className="flex gap-2">
    {(['MANUAL', 'AUTO'] as const).map((value) => <button type="button" key={value}
      disabled={disabled} aria-pressed={mode === value} onClick={() => onChange(value)}
      className={mode === value ? 'primary-button' : 'secondary-button'}>
      {value === 'MANUAL' ? 'Manual' : 'Auto'}
    </button>)}
  </div>
}
