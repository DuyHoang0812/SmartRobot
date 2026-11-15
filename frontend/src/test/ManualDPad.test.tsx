import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { ManualDPad } from '../components/control/ManualDPad'

beforeEach(() => {
  vi.stubGlobal('PointerEvent', class extends MouseEvent {
    pointerType: string
    pointerId: number
    constructor(type: string, init: PointerEventInit = {}) {
      super(type, init); this.pointerType = init.pointerType ?? 'mouse'; this.pointerId = init.pointerId ?? 1
    }
  })
})

function mount(disabled = false) {
  const start = vi.fn(), stop = vi.fn()
  const view = render(<ManualDPad disabled={disabled} onStart={start} onStop={stop} />)
  return { ...view, start, stop }
}

it('renders exactly four directions with no stop button', () => {
  mount()
  expect(screen.getAllByRole('button')).toHaveLength(4)
  expect(screen.queryByRole('button', { name: /Dừng/ })).not.toBeInTheDocument()
})

it.each([['Tiến', 'FORWARD'], ['Lùi', 'BACKWARD'], ['Quay trái', 'TURN_LEFT'], ['Quay phải', 'TURN_RIGHT']])('holds %s with a mouse and stops on release', (label, direction) => {
  const { start, stop } = mount()
  const button = screen.getByRole('button', { name: label })
  fireEvent.pointerDown(button, { pointerType: 'mouse', button: 0 })
  expect(start).toHaveBeenCalledWith(direction)
  fireEvent.pointerUp(button)
  expect(stop).toHaveBeenCalledTimes(1)
})

it('supports touch and pointer cancellation', () => {
  const { start, stop } = mount()
  const button = screen.getByRole('button', { name: 'Tiến' })
  fireEvent.pointerDown(button, { pointerType: 'touch' })
  expect(start).toHaveBeenCalledWith('FORWARD')
  fireEvent.pointerCancel(button)
  expect(stop).toHaveBeenCalledTimes(1)
})

it.each([['w', 'FORWARD'], ['ArrowUp', 'FORWARD'], ['s', 'BACKWARD'], ['ArrowDown', 'BACKWARD'], ['a', 'TURN_LEFT'], ['ArrowLeft', 'TURN_LEFT'], ['d', 'TURN_RIGHT'], ['ArrowRight', 'TURN_RIGHT']])('supports key %s without repeating requests', (key, direction) => {
  const { start, stop } = mount()
  fireEvent.keyDown(window, { key })
  fireEvent.keyDown(window, { key, repeat: true })
  expect(start).toHaveBeenCalledTimes(1)
  expect(start).toHaveBeenCalledWith(direction)
  fireEvent.keyUp(window, { key })
  expect(stop).toHaveBeenCalledTimes(1)
})

it('stops on blur and unmount', () => {
  const { stop, unmount } = mount()
  fireEvent.keyDown(window, { key: 'w' })
  fireEvent.blur(window)
  expect(stop).toHaveBeenCalledTimes(1)
  fireEvent.keyDown(window, { key: 'd' })
  unmount()
  expect(stop).toHaveBeenCalledTimes(2)
})

it('disables keyboard and pointer controls', () => {
  const { start } = mount(true)
  fireEvent.keyDown(window, { key: 'w' })
  fireEvent.pointerDown(screen.getByRole('button', { name: 'Tiến' }))
  expect(start).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: 'Tiến' })).toBeDisabled()
})

it('does not capture typing in a text input', () => {
  const { start } = mount()
  const input = document.createElement('input')
  document.body.append(input)
  fireEvent.keyDown(input, { key: 'w' })
  expect(start).not.toHaveBeenCalled()
  input.remove()
})
