// ©AngelaMos | 2026
// worm-viz.tsx

import { useMemo } from 'react'
import { useRepos } from '@/api/hooks'
import { useDashboardStore } from '@/core/lib'
import styles from './worm-viz.module.scss'

export function WormViz(): React.ReactElement {
  const { data: repos } = useRepos()
  const currentRepo = useDashboardStore((s) => s.currentRepo)
  const currentActivity = useDashboardStore((s) => s.currentActivity)

  const enabledRepos = useMemo(
    () => (repos ?? []).filter((r) => r.enabled),
    [repos]
  )

  const isActive = currentActivity !== 'idle'

  if (enabledRepos.length === 0) {
    return (
      <div className={styles.container}>
        <div className={styles.header}>
          <span className={styles.title}>Repositories</span>
        </div>
        <div className={styles.empty}>No repos configured</div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span className={styles.title}>Repositories</span>
        <span className={`${styles.statusTag} ${isActive ? styles.active : ''}`}>
          {isActive ? currentActivity : 'idle'}
        </span>
      </div>
      <div className={styles.grid}>
        {enabledRepos.map((repo) => {
          const isCurrent = repo.name === currentRepo && isActive
          return (
            <div
              key={repo.name}
              className={`${styles.node} ${isCurrent ? styles.activeNode : ''}`}
            >
              <span className={styles.nodeDot} />
              <span className={styles.nodeLabel}>
                {repo.name.split('/').pop() ?? repo.name}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
