// ©AngelaMos | 2026
// useStats.ts

import type { UseQueryResult } from '@tanstack/react-query'
import { useQuery } from '@tanstack/react-query'
import {
  DASHBOARD_ERROR_MESSAGES,
  DashboardResponseError,
  isValidStatsResponse,
  type LanguageBreakdown,
  type StatsResponse,
} from '@/api/types'
import { API_ENDPOINTS, QUERY_CONFIG, QUERY_KEYS } from '@/config'
import { apiClient } from '@/core/api'

export const statsQueries = {
  all: () => QUERY_KEYS.STATS,
  languages: () => QUERY_KEYS.LANGUAGES,
} as const

const fetchStats = async (): Promise<StatsResponse> => {
  const response = await apiClient.get<unknown>(API_ENDPOINTS.STATS)
  const data: unknown = response.data

  if (!isValidStatsResponse(data)) {
    throw new DashboardResponseError(
      DASHBOARD_ERROR_MESSAGES.INVALID_STATS_RESPONSE,
      API_ENDPOINTS.STATS
    )
  }

  return data
}

export const useStats = (): UseQueryResult<StatsResponse, Error> => {
  return useQuery({
    queryKey: statsQueries.all(),
    queryFn: fetchStats,
    staleTime: QUERY_CONFIG.STALE_TIME.STATS,
    refetchInterval: QUERY_CONFIG.STALE_TIME.STATS,
  })
}

const fetchLanguages = async (): Promise<LanguageBreakdown[]> => {
  const response = await apiClient.get<LanguageBreakdown[]>(
    API_ENDPOINTS.LANGUAGES
  )
  return response.data
}

export const useLanguages = (): UseQueryResult<
  LanguageBreakdown[],
  Error
> => {
  return useQuery({
    queryKey: statsQueries.languages(),
    queryFn: fetchLanguages,
    staleTime: QUERY_CONFIG.STALE_TIME.STATIC,
  })
}
