// ©AngelaMos | 2026
// useWebSocket.ts

import { useCallback, useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  isValidDaemonEvent,
  isValidWsMessage,
  type LogEntry,
} from '@/api/types'
import { QUERY_KEYS, WS_CONFIG } from '@/config'
import { useDashboardStore } from '@/core/lib'

const FINGERPRINT_CLEAR_MS = 30_000
const FINGERPRINT_MAX = 200

function logFingerprint(entry: Record<string, unknown>): string {
  return `${entry.event ?? ''}:${entry.timestamp ?? ''}:${entry.component ?? ''}`
}

function parseLogEntry(logData: Record<string, unknown>): LogEntry {
  return {
    id: crypto.randomUUID(),
    timestamp: (logData.timestamp as string) ?? new Date().toISOString(),
    level: (logData.log_level as string) ?? 'info',
    component: logData.component as string | undefined,
    event: logData.event as string | undefined,
    ...logData,
  }
}

export function useWebSocket(): void {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined)
  const recentFingerprints = useRef<Set<string>>(new Set())
  const cleanupTimerRef = useRef<ReturnType<typeof setInterval>>(undefined)
  const {
    setConnected,
    addLog,
    addLogs,
    setActivity,
    setNextCycleTime,
    setLastEvent,
  } = useDashboardStore()
  const queryClient = useQueryClient()

  const isDuplicate = useCallback((fp: string): boolean => {
    if (recentFingerprints.current.has(fp)) return true
    recentFingerprints.current.add(fp)
    if (recentFingerprints.current.size > FINGERPRINT_MAX) {
      const entries = [...recentFingerprints.current]
      recentFingerprints.current = new Set(entries.slice(-FINGERPRINT_MAX / 2))
    }
    return false
  }, [])

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/ws`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
    }

    ws.onclose = () => {
      setConnected(false)
      wsRef.current = null

      reconnectTimerRef.current = setTimeout(() => {
        connect()
      }, WS_CONFIG.RECONNECT_INTERVAL)
    }

    ws.onerror = () => {
      ws.close()
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const parsed: unknown = JSON.parse(event.data as string)

        if (!isValidWsMessage(parsed)) return

        const { channel, data } = parsed

        if (channel === 'codeworm:history') {
          const messages = data as Array<{ channel: string; data: unknown }>
          if (!Array.isArray(messages)) return

          const entries: LogEntry[] = []
          let lastNextCycle: string | null = null

          for (const msg of messages) {
            if (msg.channel === 'codeworm:logs') {
              const logData = msg.data as Record<string, unknown>
              const fp = logFingerprint(logData)
              if (!isDuplicate(fp)) {
                entries.push(parseLogEntry(logData))
              }
            }
            if (msg.channel === 'codeworm:events') {
              const evt = msg.data as Record<string, unknown>
              if (evt.type === 'next_cycle' && evt.data) {
                const d = evt.data as Record<string, unknown>
                lastNextCycle = (d.time as string) ?? null
              }
            }
          }
          if (entries.length > 0) {
            addLogs(entries)
          }
          if (lastNextCycle) {
            setNextCycleTime(lastNextCycle)
          }
          return
        }

        if (channel === 'codeworm:logs') {
          const logData = data as Record<string, unknown>
          const fp = logFingerprint(logData)
          if (!isDuplicate(fp)) {
            addLog(parseLogEntry(logData))
          }
        }

        if (channel === 'codeworm:events' && isValidDaemonEvent(data)) {
          setLastEvent(data)

          if (
            data.type === 'analyzing' ||
            data.type === 'generating'
          ) {
            setActivity(
              data.type,
              data.data.target as string | undefined,
              data.data.repo as string | undefined,
              data.data.doc_type as string | undefined
            )
            setNextCycleTime(null)
          }

          if (data.type === 'documentation_committed') {
            setActivity('idle')
            void queryClient.invalidateQueries({
              queryKey: QUERY_KEYS.STATS,
            })
            void queryClient.invalidateQueries({
              queryKey: ['recent'],
            })
          }

          if (data.type === 'cycle_starting') {
            setActivity('starting')
            setNextCycleTime(null)
          }

          if (data.type === 'next_cycle') {
            setNextCycleTime(
              (data.data.time as string) ?? null
            )
          }
        }

        if (channel === 'codeworm:stats') {
          void queryClient.invalidateQueries({
            queryKey: QUERY_KEYS.STATS,
          })
        }
      } catch {
        // noop
      }
    }
  }, [setConnected, addLog, addLogs, setActivity, setNextCycleTime, setLastEvent, queryClient, isDuplicate])

  useEffect(() => {
    connect()

    cleanupTimerRef.current = setInterval(() => {
      recentFingerprints.current.clear()
    }, FINGERPRINT_CLEAR_MS)

    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
      }
      if (cleanupTimerRef.current) {
        clearInterval(cleanupTimerRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [connect])
}
