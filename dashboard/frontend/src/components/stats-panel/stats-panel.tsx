// ©AngelaMos | 2026
// stats-panel.tsx

import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useLanguages, useStats } from '@/api/hooks'
import styles from './stats-panel.module.scss'

const LANG_COLORS = [
  '#c15f3c',
  '#a855f7',
  '#4ade80',
  '#facc15',
  '#ef4444',
  '#f97316',
  '#ec4899',
  '#6366f1',
]

interface TooltipProps {
  active?: boolean
  payload?: Array<{ name: string; value: number; payload: { language?: string; name?: string }; color?: string }>
}

function PieTooltip({ active, payload }: TooltipProps): React.ReactElement | null {
  if (!active || !payload?.length) return null
  const item = payload[0]
  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipRow}>
        <span className={styles.tooltipDot} style={{ background: item.color }} />
        <span className={styles.tooltipLabel}>{item.payload.language}</span>
      </div>
      <div className={styles.tooltipValue}>{item.value.toLocaleString()} docs</div>
    </div>
  )
}

function BarTooltip({ active, payload }: TooltipProps): React.ReactElement | null {
  if (!active || !payload?.length) return null
  const item = payload[0]
  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipLabel}>{item.payload.name}</div>
      <div className={styles.tooltipValue}>{item.value.toLocaleString()} docs</div>
    </div>
  )
}

function StatCard({
  label,
  value,
  highlight,
}: {
  label: string
  value: number
  highlight?: boolean
}): React.ReactElement {
  return (
    <div className={styles.statCard}>
      <div className={`${styles.statValue} ${highlight ? styles.highlight : ''}`}>
        {value.toLocaleString()}
      </div>
      <div className={styles.statLabel}>{label}</div>
    </div>
  )
}

export function StatsPanel(): React.ReactElement {
  const { data: stats } = useStats()
  const { data: languages } = useLanguages()

  const repoData = stats
    ? Object.entries(stats.by_repo)
        .map(([name, count]) => ({ name: name.split('/').pop() ?? name, count }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 8)
    : []

  return (
    <div>
      <div className={styles.grid}>
        <StatCard
          label="Total Documented"
          value={stats?.total_documented ?? 0}
          highlight
        />
        <StatCard label="Today" value={stats?.today ?? 0} />
        <StatCard label="Last 7 Days" value={stats?.last_7_days ?? 0} />
        <StatCard label="Last 30 Days" value={stats?.last_30_days ?? 0} />
      </div>

      <div className={styles.charts}>
        <div className={styles.chartCard}>
          <div className={styles.chartTitle}>Languages</div>
          {languages && languages.length > 0 ? (
            <>
              <div className={styles.chartWrap}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={languages}
                      dataKey="count"
                      nameKey="language"
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={85}
                      paddingAngle={3}
                      stroke="none"
                    >
                      {languages.map((_, i) => (
                        <Cell
                          key={languages[i].language}
                          fill={LANG_COLORS[i % LANG_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      content={<PieTooltip />}
                      cursor={false}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className={styles.legend}>
                {languages.map((lang, i) => (
                  <div key={lang.language} className={styles.legendItem}>
                    <span
                      className={styles.legendDot}
                      style={{ background: LANG_COLORS[i % LANG_COLORS.length] }}
                    />
                    <span className={styles.legendLabel}>{lang.language}</span>
                    <span className={styles.legendValue}>{lang.count}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className={styles.empty}>No data yet</div>
          )}
        </div>

        <div className={styles.chartCard}>
          <div className={styles.chartTitle}>By Repository</div>
          {repoData.length > 0 ? (
            <div className={styles.chartWrap}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={repoData} layout="vertical" barSize={14}>
                  <XAxis type="number" hide />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={100}
                    tick={{ fill: 'hsl(0, 0%, 70.6%)', fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    content={<BarTooltip />}
                    cursor={{ fill: 'hsl(0, 0%, 14.1%)' }}
                  />
                  <Bar dataKey="count" fill="#c15f3c" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className={styles.empty}>No data yet</div>
          )}
        </div>
      </div>
    </div>
  )
}
