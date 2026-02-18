// ©AngelaMos | 2026
// dashboard.types.ts

import { z } from 'zod'

export const DocType = {
  FUNCTION_DOC: 'function_doc',
  CLASS_DOC: 'class_doc',
  FILE_DOC: 'file_doc',
  MODULE_DOC: 'module_doc',
  SECURITY_REVIEW: 'security_review',
  PERFORMANCE_ANALYSIS: 'performance_analysis',
  TIL: 'til',
  CODE_EVOLUTION: 'code_evolution',
  PATTERN_ANALYSIS: 'pattern_analysis',
  WEEKLY_SUMMARY: 'weekly_summary',
  MONTHLY_SUMMARY: 'monthly_summary',
} as const

export type DocType = (typeof DocType)[keyof typeof DocType]

export const statsResponseSchema = z.object({
  total_documented: z.number(),
  by_repo: z.record(z.string(), z.number()),
  by_language: z.record(z.string(), z.number()),
  by_doc_type: z.record(z.string(), z.number()),
  last_7_days: z.number(),
  last_30_days: z.number(),
  today: z.number(),
})

export const repoStatusSchema = z.object({
  name: z.string(),
  path: z.string(),
  weight: z.number(),
  enabled: z.boolean(),
  docs_generated: z.number(),
  last_activity: z.string().nullable(),
})

export const recentDocSchema = z.object({
  id: z.string(),
  source_repo: z.string(),
  source_file: z.string(),
  function_name: z.string().nullable(),
  class_name: z.string().nullable(),
  doc_type: z.string(),
  documented_at: z.string(),
  snippet_path: z.string(),
  git_commit: z.string().nullable(),
})

export const activityDaySchema = z.object({
  date: z.string(),
  count: z.number(),
})

export const languageBreakdownSchema = z.object({
  language: z.string(),
  count: z.number(),
  percentage: z.number(),
})

export const logEntrySchema = z.object({
  timestamp: z.string().optional(),
  level: z.string().optional(),
  component: z.string().optional(),
  event: z.string().optional(),
}).passthrough()

export const daemonEventSchema = z.object({
  type: z.string(),
  timestamp: z.string(),
  data: z.record(z.string(), z.unknown()),
})

export const wsMessageSchema = z.object({
  channel: z.string(),
  data: z.unknown(),
})

export type StatsResponse = z.infer<typeof statsResponseSchema>
export type RepoStatus = z.infer<typeof repoStatusSchema>
export type RecentDoc = z.infer<typeof recentDocSchema>
export type ActivityDay = z.infer<typeof activityDaySchema>
export type LanguageBreakdown = z.infer<typeof languageBreakdownSchema>
export type LogEntry = z.infer<typeof logEntrySchema> & {
  id: string
  [key: string]: unknown
}
export type DaemonEvent = z.infer<typeof daemonEventSchema>
export type WsMessage = z.infer<typeof wsMessageSchema>

export const isValidStatsResponse = (
  data: unknown
): data is StatsResponse => {
  if (data === null || data === undefined) return false
  if (typeof data !== 'object') return false

  const result = statsResponseSchema.safeParse(data)
  return result.success
}

export const isValidRepoStatus = (
  data: unknown
): data is RepoStatus => {
  if (data === null || data === undefined) return false
  if (typeof data !== 'object') return false

  const result = repoStatusSchema.safeParse(data)
  return result.success
}

export const isValidRecentDoc = (
  data: unknown
): data is RecentDoc => {
  if (data === null || data === undefined) return false
  if (typeof data !== 'object') return false

  const result = recentDocSchema.safeParse(data)
  return result.success
}

export const isValidDaemonEvent = (
  data: unknown
): data is DaemonEvent => {
  if (data === null || data === undefined) return false
  if (typeof data !== 'object') return false

  const result = daemonEventSchema.safeParse(data)
  return result.success
}

export const isValidWsMessage = (
  data: unknown
): data is WsMessage => {
  if (data === null || data === undefined) return false
  if (typeof data !== 'object') return false

  const result = wsMessageSchema.safeParse(data)
  return result.success
}

export class DashboardResponseError extends Error {
  readonly endpoint?: string

  constructor(message: string, endpoint?: string) {
    super(message)
    this.name = 'DashboardResponseError'
    this.endpoint = endpoint
    Object.setPrototypeOf(this, DashboardResponseError.prototype)
  }
}

export const DASHBOARD_ERROR_MESSAGES = {
  INVALID_STATS_RESPONSE: 'Invalid stats data from server',
  INVALID_REPOS_RESPONSE: 'Invalid repos data from server',
  INVALID_RECENT_RESPONSE: 'Invalid recent docs from server',
  WS_CONNECTION_FAILED: 'WebSocket connection failed',
  WS_RECONNECTING: 'Reconnecting to live feed...',
} as const

export type DashboardErrorMessage =
  (typeof DASHBOARD_ERROR_MESSAGES)[keyof typeof DASHBOARD_ERROR_MESSAGES]
