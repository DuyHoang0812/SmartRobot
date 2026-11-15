import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import * as api from '../services/api'
import { RobotWebSocket } from '../services/robotWebSocket'
import { controlState, FakeRobotSocket } from './controlFixtures'

let stream: RobotWebSocket | null = null
beforeEach(() => {
  vi.useFakeTimers()
  FakeRobotSocket.instances = []
  vi.stubGlobal('WebSocket', FakeRobotSocket)
  vi.spyOn(api, 'socketAccessToken').mockResolvedValue('memory-only-token')
})
afterEach(() => { stream?.close(); vi.useRealTimers() })

it('authenticates in the first frame without URL tokens and requires a state before ready', async () => {
  const state = vi.fn(), status = vi.fn()
  stream = new RobotWebSocket('robot', state, status, vi.fn())
  await stream.start()
  const socket = FakeRobotSocket.instances[0]
  expect(socket.url).not.toContain('token')
  expect(socket.url).not.toContain('?')
  socket.open()
  expect(JSON.parse(String(socket.sent[0][0]))).toEqual({ type: 'authenticate', access_token: 'memory-only-token' })
  expect(status).not.toHaveBeenCalledWith('connected')
  socket.frame(controlState())
  expect(status).toHaveBeenCalledWith('connected')
  expect(state).toHaveBeenCalledTimes(1)
})

it('disconnects safely, reconnects with backoff and cleans up timers', async () => {
  const lose = vi.fn()
  stream = new RobotWebSocket('robot', vi.fn(), vi.fn(), lose)
  await stream.start()
  FakeRobotSocket.instances[0].disconnect()
  expect(lose).toHaveBeenCalledTimes(1)
  await vi.advanceTimersByTimeAsync(500)
  expect(FakeRobotSocket.instances).toHaveLength(2)
  stream.close()
  await vi.advanceTimersByTimeAsync(10000)
  expect(FakeRobotSocket.instances).toHaveLength(2)
})

it('stops movement when application heartbeat frames stop', async () => {
  const lose = vi.fn(), status = vi.fn()
  stream = new RobotWebSocket('robot', vi.fn(), status, lose)
  await stream.start()
  FakeRobotSocket.instances[0].open()
  await vi.advanceTimersByTimeAsync(4000)
  expect(lose).toHaveBeenCalled()
  expect(status).toHaveBeenCalledWith('disconnected')
})

it('does not reconnect when robot access is denied', async () => {
  stream = new RobotWebSocket('robot', vi.fn(), vi.fn(), vi.fn())
  await stream.start()
  FakeRobotSocket.instances[0].disconnect(4003)
  await vi.advanceTimersByTimeAsync(15000)
  expect(FakeRobotSocket.instances).toHaveLength(1)
})
