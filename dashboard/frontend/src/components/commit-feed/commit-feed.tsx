// ©AngelaMos | 2026
// commit-feed.tsx

import { useRecent } from '@/api/hooks'
import styles from './commit-feed.module.scss'

function formatDocType(dt: string): string {
  return dt
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMin = Math.floor(diffMs / 60000)

    if (diffMin < 1) return 'just now'
    if (diffMin < 60) return `${diffMin}m ago`

    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr}h ago`

    const diffDay = Math.floor(diffHr / 24)
    return `${diffDay}d ago`
  } catch {
    return ''
  }
}

function displayName(doc: {
  function_name: string | null
  class_name: string | null
  source_file: string
}): string {
  if (doc.class_name && doc.function_name) {
    return `${doc.class_name}.${doc.function_name}`
  }
  if (doc.function_name) return doc.function_name
  if (doc.class_name) return doc.class_name
  return doc.source_file.split('/').pop() ?? doc.source_file
}

export function CommitFeed(): React.ReactElement {
  const { data: recent } = useRecent(30)

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span className={styles.title}>Recent Commits</span>
        <span className={styles.count}>{recent?.length ?? 0}</span>
      </div>

      <div className={styles.list}>
        {!recent || recent.length === 0 ? (
          <div className={styles.empty}>No documentation commits yet</div>
        ) : (
          recent.map((doc) => (
            <div key={doc.id} className={styles.item}>
              <span className={styles.dot} />
              <div className={styles.itemBody}>
                <div className={styles.itemTop}>
                  <span className={styles.funcName}>{displayName(doc)}</span>
                  <span className={styles.docType}>
                    {formatDocType(doc.doc_type)}
                  </span>
                </div>
                <div className={styles.itemMeta}>
                  <span className={styles.repo}>{doc.source_repo}</span>
                  <span className={styles.sep}>&middot;</span>
                  <span>{formatTime(doc.documented_at)}</span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
