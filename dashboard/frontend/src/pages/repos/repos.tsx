// ©AngelaMos | 2026
// repos.tsx

import { useRepos } from '@/api/hooks'
import styles from './repos.module.scss'

function formatDate(iso: string | null): string {
  if (!iso) return 'Never'
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return 'Unknown'
  }
}

export function Component(): React.ReactElement {
  const { data: repos } = useRepos()

  const totalRepos = repos?.length ?? 0
  const enabledRepos = repos?.filter((r) => r.enabled).length ?? 0
  const totalDocs = repos?.reduce((sum, r) => sum + r.docs_generated, 0) ?? 0

  return (
    <div className={styles.page}>
      <div className={styles.summary}>
        <div className={styles.summaryCard}>
          <div className={styles.summaryLabel}>Total Repos</div>
          <div className={styles.summaryValue}>{totalRepos}</div>
        </div>
        <div className={styles.summaryCard}>
          <div className={styles.summaryLabel}>Active</div>
          <div className={styles.summaryValue}>{enabledRepos}</div>
        </div>
        <div className={styles.summaryCard}>
          <div className={styles.summaryLabel}>Docs Generated</div>
          <div className={styles.summaryValue}>{totalDocs.toLocaleString()}</div>
        </div>
      </div>

      <div className={styles.table}>
        <div className={styles.thead}>
          <span>Repository</span>
          <span>Weight</span>
          <span>Docs</span>
          <span className={styles.hideSmall}>Last Activity</span>
          <span className={styles.hideSmall}>Status</span>
        </div>

        {!repos || repos.length === 0 ? (
          <div className={styles.empty}>No repositories configured</div>
        ) : (
          repos.map((repo) => (
            <div key={repo.name} className={styles.row}>
              <span className={styles.name}>{repo.name}</span>
              <span className={styles.weight}>{repo.weight}</span>
              <span className={styles.docs}>{repo.docs_generated}</span>
              <span className={`${styles.lastActivity} ${styles.hideSmall}`}>
                {formatDate(repo.last_activity)}
              </span>
              <div className={`${styles.status} ${styles.hideSmall}`}>
                <span
                  className={`${styles.statusDot} ${repo.enabled ? styles.active : styles.inactive}`}
                />
                <span className={styles.statusLabel}>
                  {repo.enabled ? 'Active' : 'Disabled'}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
