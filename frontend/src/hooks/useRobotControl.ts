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
  const moving = useRef(false)
  const turn = useRef(0)
  const leaseIntent = useRef(0)
  const alive = useRef(true)
  const restoring = useRef<string | null>(null)
  const query = useQuery({ queryKey: key, queryFn: ({ signal }) => service.state(signal),
    enabled: enabled && Boolean(user), retry: false,
    refetchInterval: (query) => isRobotNotFound(query.state.error) || connection === 'connected' ? false : 5000,
    refetchOnWindowFocus: (query) => !isRobotNotFound(query.state.error),
    refetchOnReconnect: (query) => !isRobotNotFound(query.state.error) })
  const refetch = query.refetch

  const stop = useCallback(() => {
    const wasMoving = moving.current
    moving.current = false
    turn.current += 1
    if (held.current) clearTimeout(held.current)
    held.current = null
    if (!wasMoving) return
    void service.stop().then((command) => { if (command && alive.current) setAccepted(command) })
      .catch((failure: unknown) => { if (alive.current) setError(errorMessage(failure)) })
  }, [service])

  const release = useCallback(() => {
    leaseIntent.current += 1
    restoring.current = grant?.id ?? null
    stop()
    setPending(true)
    return service.release().then(() => {
      setGrant(null)
      setLeaseAlive(false)
      cache.setQueryData<ControlState>(key, (previous) => previous && {
        ...previous, lease: { id: null, owned: false, expires_at: null },
      })
      void refetch()
    }).catch((failure: unknown) => {
      if (alive.current) setError(errorMessage(failure))
    }).finally(() => { if (alive.current) setPending(false) })
  }, [service, stop, cache, key, refetch, grant?.id])

  const halt = useCallback(() => {
    stop()
  }, [stop])

  useEffect(() => {
    if (enabled) return
    const timer = setTimeout(halt, 0)
    return () => clearTimeout(timer)
  }, [enabled, halt])

  useEffect(() => {
    alive.current = true
    const lose = halt
    const hidden = () => { if (document.hidden) lose() }
    window.addEventListener('blur', lose)
    document.addEventListener('visibilitychange', hidden)
    const unsubscribeLogout = beforeLogout(async () => { stop(); await service.stop() })
    const unsubscribe = onSessionExpired(() => {
      moving.current = false
      leaseIntent.current += 1
      turn.current += 1
      if (held.current) clearTimeout(held.current)
      service.forget(); setGrant(null); setLeaseAlive(false)
    })
    return () => {
      alive.current = false
      stop()
      turn.current += 1
      if (held.current) clearTimeout(held.current)
      // Auto authorization expires independently when renew stops. Keep its selected mode.
      unsubscribe()
      unsubscribeLogout()
      window.removeEventListener('blur', lose)
      document.removeEventListener('visibilitychange', hidden)
    }
  }, [service, halt, stop])

  const hasState = enabled && Boolean(query.data)
  useEffect(() => {
    if (!hasState) return
    const socket = new RobotWebSocket(id, (data) => {
      cache.setQueryData<ControlState>(key, (previous) =>
        previous && Date.parse(previous.server_time) > Date.parse(data.server_time) ? previous : data)
    }, setConnection, halt)
    void socket.start()
    return () => socket.close()
  }, [id, hasState, cache, key, halt])

  useEffect(() => {
    if (!grant || !enabled || connection !== 'connected') return
    let finished = false
    const renew = async () => {
      if (finished) return
      try {
        const renewed = await service.renew()
        if (!finished) {
          // Keep the secret only in local state; never put a lease grant into Query cache.
          setGrant({ ...grant, expires_at: renewed.expires_at })
        }
      } catch (failure) {
        if (!finished) {
          setError(errorMessage(failure)); halt()
          // Retry even if the socket remains connected after a transient REST error.
          timer = setTimeout(() => { void renew() }, grant.renew_after_ms)
        }
      }
    }
    let timer = setTimeout(() => { void renew() }, grant.renew_after_ms)
    return () => { finished = true; clearTimeout(timer) }
  }, [grant, enabled, connection, service, halt])

  const state = query.data
  const owns = Boolean(leaseAlive && grant && state?.lease.owned && state.lease.id === grant.id)
  const canDrive = Boolean(enabled && !query.error && owns && connection === 'connected' && state?.status !== 'OFFLINE'
    && state?.actual_mode === 'MANUAL' && state.requested_mode === 'MANUAL' && !state.mode_pending
    && state.telemetry_fresh && !pending)

  const start = useCallback((direction: MoveDirection) => {
    if (!canDrive) return
    if (moving.current) stop()
    moving.current = true
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
        halt()
      }
    }
    void tick()
  }, [canDrive, stop, service, halt])

  useEffect(() => { if (!canDrive) stop() }, [canDrive, stop])

  const acquire = useCallback(async () => {
    const intent = ++leaseIntent.current
    setPending(true); setError('')
    try {
      const acquired = await service.acquire()
      if (!alive.current || intent !== leaseIntent.current) { await service.stop(); return }
      setGrant(acquired); setLeaseAlive(true); await refetch()
    }
    catch (failure) { if (alive.current) setError(errorMessage(failure)) }
    finally { if (alive.current) setPending(false) }
  }, [service, refetch])

  useEffect(() => {
    if (!enabled || !state?.lease.owned || !state.lease.id || grant || pending
      || restoring.current === state.lease.id) return
    restoring.current = state.lease.id
    // Recover credentials from the server as the authenticated borrower after reload/login.
    void acquire()
  }, [enabled, state?.lease.owned, state?.lease.id, grant, pending, acquire])
  async function mode(value: Mode) {
    stop(); setPending(true); setError('')
    try { setAccepted(await service.mode(value)); await query.refetch() }
    catch (failure) { setError(errorMessage(failure)); halt() }
    finally { setPending(false) }
  }
  const displayState = state && (connection !== 'connected' || query.error)
    ? { ...state, telemetry_fresh: false, acknowledgement: null } : state
  return { state: displayState, loading: query.isPending, queryError: query.error, error, pending, connection,
    owns, canDrive, accepted, start, stop, acquire, release, mode,
    retry: () => { setError(''); if (state?.lease.owned && !grant) void acquire(); else void refetch() } }
}
