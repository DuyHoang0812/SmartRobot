import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { CommandAcknowledgement } from '../components/control/CommandAcknowledgement'
import { ObstacleStatus } from '../components/control/ObstacleStatus'
import { controlState } from './controlFixtures'

it.each(['RECEIVED', 'APPLIED', 'REJECTED', 'FAILED'] as const)('renders %s without claiming motor movement', (status) => {
  const labels = { RECEIVED: 'Đã nhận lệnh', APPLIED: 'Đã áp dụng yêu cầu', REJECTED: 'Thiết bị từ chối', FAILED: 'Thiết bị báo lỗi' }
  render(<dl><CommandAcknowledgement state={controlState({ sequence: 3, acknowledgement: { status, sequence: 3, acknowledged_at: new Date().toISOString() } })} /></dl>)
  expect(screen.getByText(labels[status])).toBeInTheDocument()
  expect(screen.queryByText('Xe đang di chuyển')).not.toBeInTheDocument()
})

it('does not use an old acknowledgement to confirm a new command', () => {
  render(<dl><CommandAcknowledgement state={controlState({ sequence: 4, acknowledgement: { status: 'APPLIED', sequence: 3, acknowledged_at: new Date().toISOString() } })} /></dl>)
  expect(screen.getByText('Chưa xác nhận')).toBeInTheDocument()
})

it('keeps missing and stale sensor readings unknown', () => {
  const state = controlState({ telemetry_fresh: false, distance_cm: 9, obstacle: 'BLOCKED', buzzer: true })
  const view = render(<ObstacleStatus state={state} />)
  expect(screen.getByText('Chưa có dữ liệu')).toBeInTheDocument()
  expect(screen.queryByText('9 cm')).not.toBeInTheDocument()
  view.rerender(<ObstacleStatus state={{ ...state, telemetry_fresh: true, obstacle: 'SENSOR_ERROR', distance_cm: null }} />)
  expect(screen.getByText('Lỗi cảm biến')).toBeInTheDocument()
})
