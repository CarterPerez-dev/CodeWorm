// ©AngelaMos | 2026
// live-log.tsx

import { useEffect, useRef, useState } from 'react'
import { LuArrowDown, LuTrash2 } from 'react-icons/lu'
import { useDashboardStore } from '@/core/lib'
import styles from './live-log.module.scss'

const LEVEL_STYLE: Record<string, string> = {
  debug: styles.debug,
  info: styles.info,
  warning: styles.warning,
  error: styles.error,
}

function formatTime(ts?: string): string {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('en-US', { hour12: false })
  } catch {
    return ''
  }
}

export function LiveLog(): React.ReactElement {
  const logs = useDashboardStore((s) => s.logs)
  const clearLogs = useDashboardStore((s) => s.clearLogs)
  const [autoScroll, setAutoScroll] = useState(true)
  const [filter, setFilter] = useState('all')
  const scrollRef = useRef<HTMLDivElement>(null)

  const filtered =
    filter === 'all' ? logs : logs.filter((l) => l.level === filter)

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [filtered.length, autoScroll])

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span className={styles.title}>Live Log</span>
        <div className={styles.controls}>
          <select
            className={styles.filterSelect}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="all">All</option>
            <option value="debug">Debug</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
          </select>
          <button
            type="button"
            className={`${styles.controlBtn} ${autoScroll ? styles.active : ''}`}
            onClick={() => setAutoScroll(!autoScroll)}
            aria-label="Toggle auto-scroll"
          >
            <LuArrowDown />
          </button>
          <button
            type="button"
            className={styles.controlBtn}
            onClick={clearLogs}
            aria-label="Clear logs"
          >
            <LuTrash2 />
          </button>
        </div>
      </div>

      <div className={styles.logArea} ref={scrollRef}>
        {filtered.length === 0 ? (
          <div className={styles.empty}>Waiting for logs...</div>
        ) : (
          filtered.map((log) => (
            <div key={log.id} className={styles.logLine}>
              <span className={styles.logTime}>
                {formatTime(log.timestamp)}
              </span>
              <span
                className={`${styles.logLevel} ${LEVEL_STYLE[log.level ?? ''] ?? ''}`}
              >
                {log.level ?? '???'}
              </span>
              <span className={styles.logComponent}>
                {log.component ?? ''}
              </span>
              <span className={styles.logEvent}>{log.event ?? ''}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
