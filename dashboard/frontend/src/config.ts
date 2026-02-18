// ©AngelaMos | 2026
// config.ts

export const API_ENDPOINTS = {
  STATS: '/stats',
  REPOS: '/repos',
  RECENT: '/recent',
  ACTIVITY: '/activity',
  LANGUAGES: '/languages',
} as const

export const QUERY_KEYS = {
  STATS: ['stats'] as const,
  REPOS: ['repos'] as const,
  RECENT: (page: number, repo?: string, docType?: string) =>
    ['recent', { page, repo, docType }] as const,
  ACTIVITY: (days: number) => ['activity', days] as const,
  LANGUAGES: ['languages'] as const,
} as const

export const ROUTES = {
  DASHBOARD: '/',
  REPOS: '/repos',
} as const

export const STORAGE_KEYS = {
  UI: 'codeworm-ui',
  DASHBOARD: 'codeworm-dashboard',
} as const

export const QUERY_CONFIG = {
  STALE_TIME: {
    STATS: 1000 * 15,
    FREQUENT: 1000 * 30,
    STATIC: 1000 * 60 * 5,
  },
  GC_TIME: {
    DEFAULT: 1000 * 60 * 30,
  },
  RETRY: {
    DEFAULT: 3,
    NONE: 0,
  },
} as const

export const WS_CONFIG = {
  RECONNECT_INTERVAL: 3000,
  MAX_LOG_ENTRIES: 500,
} as const
