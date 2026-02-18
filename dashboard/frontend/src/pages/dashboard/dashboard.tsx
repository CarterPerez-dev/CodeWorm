// ©AngelaMos | 2026
// dashboard.tsx

import {
  CommitFeed,
  CurrentActivity,
  LiveLog,
  StatsPanel,
  WormViz,
} from '@/components'
import styles from './dashboard.module.scss'

export function Component(): React.ReactElement {
  return (
    <div className={styles.page}>
      <StatsPanel />

      <div className={styles.middle}>
        <CurrentActivity />
        <WormViz />
      </div>

      <div className={styles.bottom}>
        <LiveLog />
        <CommitFeed />
      </div>
    </div>
  )
}
