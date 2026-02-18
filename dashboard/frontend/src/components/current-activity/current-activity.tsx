// ©AngelaMos | 2026
// current-activity.tsx

import { useEffect, useState } from 'react'
import { useDashboardStore } from '@/core/lib'
import styles from './current-activity.module.scss'

const STATUS_STYLE: Record<string, string> = {
  analyzing: styles.analyzing,
  generating: styles.generating,
  committing: styles.committing,
}

function formatDocType(dt: string): string {
  return dt
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function formatCountdown(targetIso: string): string | null {
  const target = new Date(targetIso).getTime()
  const now = Date.now()
  const diff = target - now

  if (diff <= 0) return null

  const totalSec = Math.floor(diff / 1000)
  const hours = Math.floor(totalSec / 3600)
  const minutes = Math.floor((totalSec % 3600) / 60)
  const seconds = totalSec % 60

  if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`
  }
  return `${seconds}s`
}

export function CurrentActivity(): React.ReactElement {
  const {
    currentActivity,
    currentTarget,
    currentRepo,
    currentDocType,
    nextCycleTime,
  } = useDashboardStore()
  const [countdown, setCountdown] = useState<string | null>(null)

  const isIdle = currentActivity === 'idle'

  useEffect(() => {
    if (!isIdle || !nextCycleTime) {
      setCountdown(null)
      return
    }

    const tick = () => {
      const result = formatCountdown(nextCycleTime)
      setCountdown(result)
    }

    tick()
    const interval = setInterval(tick, 1000)
    return () => clearInterval(interval)
  }, [isIdle, nextCycleTime])

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span className={styles.title}>Current Activity</span>
        <span
          className={`${styles.statusBadge} ${STATUS_STYLE[currentActivity] ?? ''}`}
        >
          {currentActivity}
        </span>
      </div>

      {isIdle ? (
        <div className={styles.idle}>
          <span className={styles.idleDot} />
          {countdown
            ? `Next cycle in ${countdown}`
            : 'Waiting for next cycle...'}
        </div>
      ) : (
        <div className={styles.details}>
          {currentRepo && (
            <div className={styles.row}>
              <span className={styles.rowLabel}>Repo</span>
              <span className={styles.rowValue}>{currentRepo}</span>
            </div>
          )}
          {currentTarget && (
            <div className={styles.row}>
              <span className={styles.rowLabel}>Target</span>
              <span className={styles.rowValue}>{currentTarget}</span>
            </div>
          )}
          {currentDocType && (
            <div className={styles.row}>
              <span className={styles.rowLabel}>Type</span>
              <span className={styles.docTypeBadge}>
                {formatDocType(currentDocType)}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
