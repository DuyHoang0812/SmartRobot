import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from './useAuth'
import { isRobotNotFound } from './useRobots'
import { beforeLogout, errorMessage, onSessionExpired } from '../services/api'
import { RobotControlService } from '../services/robotControlService'
import { RobotWebSocket } from '../services/robotWebSocket'
import type { ControlState, LeaseGrant, Mode, MoveDirection, RobotCommand, SocketStatus } from '../types/control'

export function useRobotControl(id: string, enabled: boolean) {
  const { user } = useAuth()
  const cache = useQueryClient()
  const service = useMemo(() => new RobotControlService(id), [id])
  const key = useMemo(() => ['robot-control', user?.id, id], [id, user?.id])
  const [connection, setConnection] = useState<SocketStatus>('connecting')
  const [grant, setGrant] = useState<LeaseGrant | null>(null)
  const [leaseAlive, setLeaseAlive] = useState(false)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const [accepted, setAccepted] = useState<RobotCommand | null>(null)
  const held = useRef<ReturnType<typeof setTimeout> | null>(null)
  const turn = useRef(0)
  const leaseIntent = useRef(0)
  const alive = useRef(true)
  const query = useQuery({ queryKey: key, queryFn: ({ signal }) => service.state(signal),
    enabled: enabled && Boolean(user), retry: false,
    refetchInterval: (query) => isRobotNotFound(query.state.error) || connection === 'connected' ? false : 5000,
    refetchOnWindowFocus: (query) => !isRobotNotFound(query.state.error),
    refetchOnReconnect: (query) => !isRobotNotFound(query.state.error) })

  const stop = useCallback(() => {
    turn.current += 1
    if (held.current) clearTimeout(held.current)
    held.current = null
    void service.stop().then((command) => { if (command && alive.current) setAccepted(command) })
      .catch((failure: unknown) => { if (alive.current) setError(errorMessage(failure)) })
  }, [service])

  const release = useCallback(() => {
    leaseIntent.current += 1
    stop()
    setGrant(null)
    setLeaseAlive(false)
    return service.release().catch((failure: unknown) => {
      if (alive.current) setError(errorMessage(failure))
    })
  }, [service, stop])

  useEffect(() => {
    if (enabled) return
    const timer = setTimeout(() => { void release() }, 0)
    return () => clearTimeout(timer)
  }, [enabled, release])

  useEffect(() => {
    alive.current = true
    const lose = () => { void release() }
    const hidden = () => { if (document.hidden) lose() }
    window.addEventListener('blur', lose)
    document.addEventListener('visibilitychange', hidden)
    const unsubscribeLogout = beforeLogout(release)
    const unsubscribe = onSessionExpired(() => {
      leaseIntent.current += 1
      turn.current += 1
      if (held.current) clearTimeout(held.current)
      service.forget(); setGrant(null); setLeaseAlive(false)
    })
    return () => {
      alive.current = false
      turn.current += 1
      if (held.current) clearTimeout(held.current)
      void service.release().catch(() => {})
      unsubscribe()
      unsubscribeLogout()
      window.removeEventListener('blur', lose)
      document.removeEventListener('visibilitychange', hidden)
    }
  }, [service, release])

  const hasState = enabled && Boolean(query.data)
  useEffect(() => {
    if (!hasState) return
    const socket = new RobotWebSocket(id, (data) => {
      cache.setQueryData<ControlState>(key, (previous) =>
        previous && Date.parse(previous.server_time) > Date.parse(data.server_time) ? previous : data)
    }, setConnection, () => { void release() })
    void socket.start()
    return () => socket.close()
  }, [id, hasState, cache, key, release])

  useEffect(() => {
    if (!grant || connection !== 'connected') return
    let finished = false
    const renew = async () => {
      if (finished) return
      if (Date.now() >= Date.parse(grant.expires_at)) { await release(); return }
      try {
        const renewed = await service.renew()
        if (!renewed.expires_at) throw new Error('Lease expired')
        if (!finished) {
          // Keep the secret only in local state; never put a lease grant into Query cache.
          setGrant({ ...grant, expires_at: renewed.expires_at })
        }
      } catch (failure) {
        if (!finished) { setError(errorMessage(failure)); await release() }
      }
    }
    const timer = setTimeout(() => { void renew() }, grant.renew_after_ms)
    return () => { finished = true; clearTimeout(timer) }
  }, [grant, connection, service, release])

  useEffect(() => {
    if (!grant) return
    const timer = setTimeout(() => { setLeaseAlive(false); void release() },
      Math.max(0, Date.parse(grant.expires_at) - Date.now()))
    return () => clearTimeout(timer)
  }, [grant, release])

  const state = query.data
  const owns = Boolean(leaseAlive && grant && state?.lease.owned && state.lease.id === grant.id)
  const canDrive = Boolean(enabled && !query.error && owns && connection === 'connected' && state?.status !== 'OFFLINE'
    && state?.actual_mode === 'MANUAL' && state.requested_mode === 'MANUAL' && !state.mode_pending
    && state.telemetry_fresh && !pending)

  const start = useCallback((direction: MoveDirection) => {
    if (!canDrive) return
    stop()
    const intent = service.beginIntent()
    const currentTurn = ++turn.current
    const tick = async () => {
      if (currentTurn !== turn.current) return
      try {
        const command = await service.move(direction, intent)
        if (currentTurn !== turn.current) return
        if (command && alive.current) setAccepted(command)
        held.current = setTimeout(() => { void tick() }, 250)
      } catch (failure) {
        if (alive.current) setError(errorMessage(failure))
        await release()
      }
    }
    void tick()
  }, [canDrive, stop, service, release])

  useEffect(() => { if (!canDrive) stop() }, [canDrive, stop])

  async function acquire() {
    const intent = ++leaseIntent.current
    setPending(true); setError('')
    try {
      const acquired = await service.acquire()
      if (!alive.current || intent !== leaseIntent.current) { await service.release(); return }
      setGrant(acquired); setLeaseAlive(true); await query.refetch()
    }
    catch (failure) { if (alive.current) setError(errorMessage(failure)) }
    finally { if (alive.current) setPending(false) }
  }
  async function mode(value: Mode) {
    stop(); setPending(true); setError('')
    try { setAccepted(await service.mode(value)); await query.refetch() }
    catch (failure) { setError(errorMessage(failure)); await release() }
    finally { setPending(false) }
  }
  const displayState = state && (connection !== 'connected' || query.error)
    ? { ...state, telemetry_fresh: false, acknowledgement: null } : state
  return { state: displayState, loading: query.isPending, queryError: query.error, error, pending, connection,
    owns, canDrive, accepted, start, stop, acquire, release, mode,
    retry: () => { setError(''); void query.refetch() } }
}
