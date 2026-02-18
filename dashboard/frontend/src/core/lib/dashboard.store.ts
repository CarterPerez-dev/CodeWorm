// ©AngelaMos | 2026
// dashboard.store.ts

import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import type { LogEntry, DaemonEvent } from '@/api/types'
import { WS_CONFIG } from '@/config'

interface DashboardState {
  connected: boolean
  logs: LogEntry[]
  currentActivity: string
  currentTarget: string | null
  currentRepo: string | null
  currentDocType: string | null
  nextCycleTime: string | null
  lastEvent: DaemonEvent | null

  setConnected: (connected: boolean) => void
  addLog: (log: LogEntry) => void
  addLogs: (logs: LogEntry[]) => void
  clearLogs: () => void
  setActivity: (activity: string, target?: string, repo?: string, docType?: string) => void
  setNextCycleTime: (time: string | null) => void
  setLastEvent: (event: DaemonEvent) => void
}

export const useDashboardStore = create<DashboardState>()(
  devtools(
    (set) => ({
      connected: false,
      logs: [],
      currentActivity: 'idle',
      currentTarget: null,
      currentRepo: null,
      currentDocType: null,
      nextCycleTime: null,
      lastEvent: null,

      setConnected: (connected) =>
        set({ connected }, false, 'dashboard/setConnected'),

      addLog: (log) =>
        set(
          (state) => ({
            logs:
              state.logs.length >= WS_CONFIG.MAX_LOG_ENTRIES
                ? [...state.logs.slice(-WS_CONFIG.MAX_LOG_ENTRIES + 1), log]
                : [...state.logs, log],
          }),
          false,
          'dashboard/addLog'
        ),

      addLogs: (newLogs) =>
        set(
          (state) => {
            const combined = [...state.logs, ...newLogs]
            return {
              logs: combined.length > WS_CONFIG.MAX_LOG_ENTRIES
                ? combined.slice(-WS_CONFIG.MAX_LOG_ENTRIES)
                : combined,
            }
          },
          false,
          'dashboard/addLogs'
        ),

      clearLogs: () => set({ logs: [] }, false, 'dashboard/clearLogs'),

      setActivity: (activity, target, repo, docType) =>
        set(
          {
            currentActivity: activity,
            currentTarget: target ?? null,
            currentRepo: repo ?? null,
            currentDocType: docType ?? null,
          },
          false,
          'dashboard/setActivity'
        ),

      setNextCycleTime: (time) =>
        set({ nextCycleTime: time }, false, 'dashboard/setNextCycleTime'),

      setLastEvent: (event) =>
        set({ lastEvent: event }, false, 'dashboard/setLastEvent'),
    }),
    { name: 'DashboardStore' }
  )
)
