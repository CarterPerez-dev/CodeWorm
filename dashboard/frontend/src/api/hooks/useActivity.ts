// ©AngelaMos | 2026
// useActivity.ts

import type { UseQueryResult } from '@tanstack/react-query'
import { useQuery } from '@tanstack/react-query'
import type { ActivityDay } from '@/api/types'
import { API_ENDPOINTS, QUERY_CONFIG, QUERY_KEYS } from '@/config'
import { apiClient } from '@/core/api'

export const activityQueries = {
  byDays: (days: number) => QUERY_KEYS.ACTIVITY(days),
} as const

const fetchActivity = async (days: number): Promise<ActivityDay[]> => {
  const response = await apiClient.get<ActivityDay[]>(
    API_ENDPOINTS.ACTIVITY,
    { params: { days } }
  )
  return response.data
}

export const useActivity = (
  days = 90
): UseQueryResult<ActivityDay[], Error> => {
  return useQuery({
    queryKey: activityQueries.byDays(days),
    queryFn: () => fetchActivity(days),
    staleTime: QUERY_CONFIG.STALE_TIME.STATIC,
  })
}
